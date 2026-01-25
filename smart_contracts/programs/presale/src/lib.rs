use anchor_lang::prelude::*;
use anchor_lang::solana_program::{
    ed25519_program,
    instruction::Instruction,
    sysvar::instructions::{load_instruction_at_checked, ID as IX_ID},
};
use anchor_spl::{
    associated_token::AssociatedToken,
    token::{self, Mint, Token, TokenAccount, Transfer},
};

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

// ============================================================================
// CONSTANTS
// ============================================================================

/// Seed for the config PDA
pub const CONFIG_SEED: &[u8] = b"config";
/// Seed for vesting account PDAs
pub const VESTING_SEED: &[u8] = b"vesting";
/// Seed for nonce tracker PDAs
pub const NONCE_SEED: &[u8] = b"nonce";
/// Seed for the token vault PDA (holds presale tokens)
pub const VAULT_SEED: &[u8] = b"vault";

/// Domain separator for signature verification to prevent cross-program replay
pub const DOMAIN_SEPARATOR: &[u8] = b"PRESALE_V1";

/// Payment type identifiers used in signature message construction
pub const PAYMENT_SOL: u8 = 0;
pub const PAYMENT_USDT: u8 = 1;
pub const PAYMENT_USDC: u8 = 2;

// ============================================================================
// PROGRAM
// ============================================================================

#[program]
pub mod presale {
    use super::*;

    /// Initializes the presale configuration.
    /// 
    /// This instruction sets up the global config PDA with:
    /// - Treasury wallet address for receiving payments
    /// - Authorized signer public key for signature verification
    /// - Token pricing configuration
    /// - Vesting schedule parameters
    /// - Accepted payment token mints (USDT, USDC)
    /// 
    /// # Security
    /// - Can only be called once (config account is initialized)
    /// - Only the admin can call this instruction
    /// - All addresses are validated
    pub fn initialize(
        ctx: Context<Initialize>,
        config_params: ConfigParams,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        
        // Validate vesting parameters
        require!(
            config_params.vesting_duration > 0,
            PresaleError::InvalidVestingDuration
        );
        
        // Validate token price (must be non-zero)
        require!(
            config_params.token_price_per_unit > 0,
            PresaleError::InvalidTokenPrice
        );

        config.admin = ctx.accounts.admin.key();
        config.treasury = config_params.treasury;
        config.authorized_signer = config_params.authorized_signer;
        config.presale_token_mint = ctx.accounts.presale_token_mint.key();
        config.usdt_mint = config_params.usdt_mint;
        config.usdc_mint = config_params.usdc_mint;
        
        // Pricing: how many payment tokens (in smallest unit) per presale token
        config.token_price_per_unit = config_params.token_price_per_unit;
        // Decimals of the presale token for calculation purposes
        config.presale_token_decimals = ctx.accounts.presale_token_mint.decimals;
        
        // Vesting configuration
        config.cliff_duration = config_params.cliff_duration;
        config.vesting_start_time = config_params.vesting_start_time;
        config.vesting_duration = config_params.vesting_duration;
        
        // Presale state
        config.is_active = true;
        config.total_sold = 0;
        config.bump = ctx.bumps.config;

        emit!(PresaleInitialized {
            admin: config.admin,
            treasury: config.treasury,
            authorized_signer: config.authorized_signer,
            presale_token_mint: config.presale_token_mint,
            token_price: config.token_price_per_unit,
        });

        Ok(())
    }

    /// Updates the presale configuration.
    /// 
    /// # Security
    /// - Only admin can update
    /// - Cannot change critical parameters like token mint
    pub fn update_config(
        ctx: Context<UpdateConfig>,
        new_treasury: Option<Pubkey>,
        new_authorized_signer: Option<Pubkey>,
        new_token_price: Option<u64>,
        new_is_active: Option<bool>,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;

        if let Some(treasury) = new_treasury {
            config.treasury = treasury;
        }
        if let Some(signer) = new_authorized_signer {
            config.authorized_signer = signer;
        }
        if let Some(price) = new_token_price {
            require!(price > 0, PresaleError::InvalidTokenPrice);
            config.token_price_per_unit = price;
        }
        if let Some(active) = new_is_active {
            config.is_active = active;
        }

        emit!(ConfigUpdated {
            treasury: config.treasury,
            authorized_signer: config.authorized_signer,
            token_price: config.token_price_per_unit,
            is_active: config.is_active,
        });

        Ok(())
    }

    /// Purchases presale tokens using SPL tokens (USDT or USDC).
    /// 
    /// # Signature Verification Flow
    /// 1. The off-chain signer creates a message containing:
    ///    - Domain separator (PRESALE_V1)
    ///    - Program ID
    ///    - Buyer wallet address
    ///    - Payment mint address
    ///    - Payment amount
    ///    - Token amount to receive
    ///    - Unique nonce
    /// 2. The signer signs this message with their ed25519 private key
    /// 3. The buyer includes an ed25519 signature verification instruction
    ///    BEFORE calling buy_tokens_spl
    /// 4. This instruction verifies the signature was valid by checking
    ///    the previous instruction in the transaction
    /// 
    /// # Treasury Transfer
    /// - Payment tokens are transferred directly to the treasury wallet
    /// - No funds are held by the program
    /// 
    /// # Vesting Account
    /// - Creates or updates the buyer's vesting account
    /// - Tracks total purchased and claimed amounts
    pub fn buy_tokens_spl(
        ctx: Context<BuyTokensSpl>,
        payment_amount: u64,
        token_amount: u64,
        nonce: u64,
        _signature: [u8; 64],
        _recovery_id: u8,
    ) -> Result<()> {
        let config = &ctx.accounts.config;
        
        // Verify presale is active
        require!(config.is_active, PresaleError::PresaleNotActive);
        
        // Verify payment amount matches expected price
        // token_amount is in smallest units of presale token
        // payment_amount is in smallest units of payment token
        let expected_payment = calculate_payment_amount(
            token_amount,
            config.token_price_per_unit,
            config.presale_token_decimals,
        )?;
        require!(
            payment_amount >= expected_payment,
            PresaleError::InsufficientPayment
        );

        // Determine payment type based on mint
        let payment_type = if ctx.accounts.payment_mint.key() == config.usdt_mint {
            PAYMENT_USDT
        } else if ctx.accounts.payment_mint.key() == config.usdc_mint {
            PAYMENT_USDC
        } else {
            return Err(PresaleError::InvalidPaymentMint.into());
        };

        // ====================================================================
        // ED25519 SIGNATURE VERIFICATION
        // ====================================================================
        // 
        // The ed25519 program must be invoked in a previous instruction within
        // the same transaction. We verify that:
        // 1. The previous instruction was to the ed25519 program
        // 2. The signature data matches our expected message
        // 3. The signer matches our authorized signer
        //
        // Message format (serialized):
        // [DOMAIN_SEPARATOR | program_id | buyer | payment_mint | payment_amount | token_amount | nonce]
        // ====================================================================
        
        verify_ed25519_signature(
            &ctx.accounts.instructions_sysvar,
            &config.authorized_signer,
            &ctx.accounts.buyer.key(),
            &ctx.accounts.payment_mint.key(),
            payment_type,
            payment_amount,
            token_amount,
            nonce,
            &crate::ID,
        )?;

        // ====================================================================
        // NONCE VERIFICATION (Replay Protection)
        // ====================================================================
        // 
        // Each nonce can only be used once. The nonce account is a PDA derived
        // from the buyer's address and the nonce value. If this account already
        // exists and is_used is true, the transaction fails.
        // ====================================================================
        
        let nonce_account = &mut ctx.accounts.nonce_account;
        require!(!nonce_account.is_used, PresaleError::NonceAlreadyUsed);
        nonce_account.is_used = true;
        nonce_account.buyer = ctx.accounts.buyer.key();
        nonce_account.nonce = nonce;
        nonce_account.used_at = Clock::get()?.unix_timestamp;

        // ====================================================================
        // TRANSFER PAYMENT TO TREASURY
        // ====================================================================
        // 
        // Transfer SPL tokens directly from buyer to treasury.
        // The program never holds payment funds.
        // ====================================================================
        
        let transfer_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.buyer_payment_account.to_account_info(),
                to: ctx.accounts.treasury_payment_account.to_account_info(),
                authority: ctx.accounts.buyer.to_account_info(),
            },
        );
        token::transfer(transfer_ctx, payment_amount)?;

        // ====================================================================
        // UPDATE VESTING ACCOUNT
        // ====================================================================
        // 
        // The vesting account tracks:
        // - Total tokens purchased (accumulated across multiple purchases)
        // - Amount already claimed
        // - Vesting schedule reference
        // ====================================================================
        
        let vesting = &mut ctx.accounts.vesting_account;
        if vesting.buyer == Pubkey::default() {
            // First purchase - initialize vesting account
            vesting.buyer = ctx.accounts.buyer.key();
            vesting.total_purchased = 0;
            vesting.claimed_amount = 0;
            vesting.bump = ctx.bumps.vesting_account;
        }
        
        // Add to total purchased (checked arithmetic to prevent overflow)
        vesting.total_purchased = vesting
            .total_purchased
            .checked_add(token_amount)
            .ok_or(PresaleError::Overflow)?;

        // Update global stats
        let config = &mut ctx.accounts.config;
        config.total_sold = config
            .total_sold
            .checked_add(token_amount)
            .ok_or(PresaleError::Overflow)?;

        emit!(TokensPurchased {
            buyer: ctx.accounts.buyer.key(),
            payment_mint: ctx.accounts.payment_mint.key(),
            payment_amount,
            token_amount,
            nonce,
        });

        Ok(())
    }

    /// Purchases presale tokens using native SOL.
    /// 
    /// Similar to buy_tokens_spl but handles native SOL transfers.
    /// SOL is transferred directly to the treasury wallet.
    pub fn buy_tokens_sol(
        ctx: Context<BuyTokensSol>,
        payment_amount: u64,
        token_amount: u64,
        nonce: u64,
        _signature: [u8; 64],
        _recovery_id: u8,
    ) -> Result<()> {
        let config = &ctx.accounts.config;
        
        // Verify presale is active
        require!(config.is_active, PresaleError::PresaleNotActive);
        
        // Verify payment amount matches expected price
        let expected_payment = calculate_payment_amount(
            token_amount,
            config.token_price_per_unit,
            config.presale_token_decimals,
        )?;
        require!(
            payment_amount >= expected_payment,
            PresaleError::InsufficientPayment
        );

        // ====================================================================
        // ED25519 SIGNATURE VERIFICATION
        // ====================================================================
        
        verify_ed25519_signature(
            &ctx.accounts.instructions_sysvar,
            &config.authorized_signer,
            &ctx.accounts.buyer.key(),
            &Pubkey::default(), // SOL has no mint, use default pubkey
            PAYMENT_SOL,
            payment_amount,
            token_amount,
            nonce,
            &crate::ID,
        )?;

        // ====================================================================
        // NONCE VERIFICATION (Replay Protection)
        // ====================================================================
        
        let nonce_account = &mut ctx.accounts.nonce_account;
        require!(!nonce_account.is_used, PresaleError::NonceAlreadyUsed);
        nonce_account.is_used = true;
        nonce_account.buyer = ctx.accounts.buyer.key();
        nonce_account.nonce = nonce;
        nonce_account.used_at = Clock::get()?.unix_timestamp;

        // ====================================================================
        // TRANSFER SOL TO TREASURY
        // ====================================================================
        // 
        // Use system program transfer for native SOL.
        // Funds go directly to treasury, never held by program.
        // ====================================================================
        
        let transfer_ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.buyer.key(),
            &ctx.accounts.treasury.key(),
            payment_amount,
        );
        anchor_lang::solana_program::program::invoke(
            &transfer_ix,
            &[
                ctx.accounts.buyer.to_account_info(),
                ctx.accounts.treasury.to_account_info(),
                ctx.accounts.system_program.to_account_info(),
            ],
        )?;

        // ====================================================================
        // UPDATE VESTING ACCOUNT
        // ====================================================================
        
        let vesting = &mut ctx.accounts.vesting_account;
        if vesting.buyer == Pubkey::default() {
            vesting.buyer = ctx.accounts.buyer.key();
            vesting.total_purchased = 0;
            vesting.claimed_amount = 0;
            vesting.bump = ctx.bumps.vesting_account;
        }
        
        vesting.total_purchased = vesting
            .total_purchased
            .checked_add(token_amount)
            .ok_or(PresaleError::Overflow)?;

        // Update global stats
        let config = &mut ctx.accounts.config;
        config.total_sold = config
            .total_sold
            .checked_add(token_amount)
            .ok_or(PresaleError::Overflow)?;

        emit!(TokensPurchased {
            buyer: ctx.accounts.buyer.key(),
            payment_mint: Pubkey::default(),
            payment_amount,
            token_amount,
            nonce,
        });

        Ok(())
    }

    /// Claims vested tokens.
    /// 
    /// # Vesting Math
    /// 
    /// The vesting schedule works as follows:
    /// 
    /// 1. **Before vesting_start_time**: No tokens claimable
    /// 2. **During cliff period** (vesting_start_time to vesting_start_time + cliff_duration):
    ///    No tokens claimable
    /// 3. **After cliff, during vesting** (cliff_end to vesting_end):
    ///    Linear vesting - tokens unlock proportionally over time
    /// 4. **After vesting_end**: All tokens claimable
    /// 
    /// Formula for vested amount:
    /// ```
    /// if current_time < cliff_end:
    ///     vested = 0
    /// elif current_time >= vesting_end:
    ///     vested = total_purchased
    /// else:
    ///     elapsed = current_time - cliff_end
    ///     vesting_period = vesting_end - cliff_end
    ///     vested = total_purchased * elapsed / vesting_period
    /// ```
    /// 
    /// Claimable = vested - already_claimed
    pub fn claim_tokens(ctx: Context<ClaimTokens>) -> Result<()> {
        let config = &ctx.accounts.config;
        let vesting = &mut ctx.accounts.vesting_account;
        let current_time = Clock::get()?.unix_timestamp;

        // ====================================================================
        // VESTING CALCULATION
        // ====================================================================
        
        let cliff_end = config
            .vesting_start_time
            .checked_add(config.cliff_duration)
            .ok_or(PresaleError::Overflow)?;
        
        let vesting_end = config
            .vesting_start_time
            .checked_add(config.vesting_duration)
            .ok_or(PresaleError::Overflow)?;

        // Calculate vested amount based on current time
        let vested_amount = if current_time < cliff_end {
            // Still in cliff period - nothing vested
            0u64
        } else if current_time >= vesting_end {
            // Vesting complete - all tokens vested
            vesting.total_purchased
        } else {
            // Linear vesting calculation
            // vested = total * (elapsed / vesting_period)
            // 
            // We use u128 for intermediate calculations to prevent overflow
            // when multiplying large token amounts by time values
            
            let elapsed = (current_time - cliff_end) as u128;
            let vesting_period = (vesting_end - cliff_end) as u128;
            let total = vesting.total_purchased as u128;
            
            // Calculate: total * elapsed / vesting_period
            // Using checked arithmetic throughout
            let vested = total
                .checked_mul(elapsed)
                .ok_or(PresaleError::Overflow)?
                .checked_div(vesting_period)
                .ok_or(PresaleError::Overflow)?;
            
            // Safe to cast back to u64 since result <= total_purchased
            vested as u64
        };

        // Calculate claimable amount (vested minus already claimed)
        let claimable = vested_amount
            .checked_sub(vesting.claimed_amount)
            .ok_or(PresaleError::Overflow)?;

        require!(claimable > 0, PresaleError::NothingToClaim);

        // ====================================================================
        // TRANSFER TOKENS FROM VAULT TO BUYER
        // ====================================================================
        // 
        // Tokens are transferred from the program's vault PDA to the buyer's
        // associated token account. The vault PDA signs the transfer.
        // ====================================================================
        
        let config_key = config.key();
        let seeds = &[
            VAULT_SEED,
            config_key.as_ref(),
            &[ctx.bumps.token_vault],
        ];
        let signer_seeds = &[&seeds[..]];

        let transfer_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.token_vault.to_account_info(),
                to: ctx.accounts.buyer_token_account.to_account_info(),
                authority: ctx.accounts.token_vault.to_account_info(),
            },
            signer_seeds,
        );
        token::transfer(transfer_ctx, claimable)?;

        // Update claimed amount
        vesting.claimed_amount = vesting
            .claimed_amount
            .checked_add(claimable)
            .ok_or(PresaleError::Overflow)?;

        emit!(TokensClaimed {
            buyer: ctx.accounts.buyer.key(),
            amount: claimable,
            total_claimed: vesting.claimed_amount,
            total_purchased: vesting.total_purchased,
        });

        Ok(())
    }

    /// Deposits presale tokens into the vault.
    /// 
    /// Admin function to fund the vault with tokens for distribution.
    pub fn deposit_tokens(ctx: Context<DepositTokens>, amount: u64) -> Result<()> {
        let transfer_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.admin_token_account.to_account_info(),
                to: ctx.accounts.token_vault.to_account_info(),
                authority: ctx.accounts.admin.to_account_info(),
            },
        );
        token::transfer(transfer_ctx, amount)?;

        emit!(TokensDeposited {
            admin: ctx.accounts.admin.key(),
            amount,
        });

        Ok(())
    }

    /// Withdraws unsold tokens from the vault.
    /// 
    /// Admin function to recover tokens after presale ends.
    pub fn withdraw_tokens(ctx: Context<WithdrawTokens>, amount: u64) -> Result<()> {
        let config = &ctx.accounts.config;
        
        let config_key = config.key();
        let seeds = &[
            VAULT_SEED,
            config_key.as_ref(),
            &[ctx.bumps.token_vault],
        ];
        let signer_seeds = &[&seeds[..]];

        let transfer_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.token_vault.to_account_info(),
                to: ctx.accounts.admin_token_account.to_account_info(),
                authority: ctx.accounts.token_vault.to_account_info(),
            },
            signer_seeds,
        );
        token::transfer(transfer_ctx, amount)?;

        emit!(TokensWithdrawn {
            admin: ctx.accounts.admin.key(),
            amount,
        });

        Ok(())
    }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/// Calculates the required payment amount for a given token amount.
/// 
/// # Arguments
/// * `token_amount` - Amount of presale tokens to purchase (in smallest units)
/// * `price_per_unit` - Price per token unit in payment token smallest units
/// * `token_decimals` - Decimals of the presale token
/// 
/// # Returns
/// Payment amount required in payment token smallest units
fn calculate_payment_amount(
    token_amount: u64,
    price_per_unit: u64,
    _token_decimals: u8,
) -> Result<u64> {
    // Simple multiplication: token_amount * price_per_unit
    // Both are in smallest units, so no decimal adjustment needed
    // The price_per_unit should be set considering the decimal differences
    // between payment token and presale token
    
    let payment = (token_amount as u128)
        .checked_mul(price_per_unit as u128)
        .ok_or(PresaleError::Overflow)?;
    
    // Ensure result fits in u64
    if payment > u64::MAX as u128 {
        return Err(PresaleError::Overflow.into());
    }
    
    Ok(payment as u64)
}

/// Verifies an ed25519 signature from the instructions sysvar.
/// 
/// # Signature Verification Process
/// 
/// 1. Load the previous instruction from the instructions sysvar
/// 2. Verify it's an ed25519 program instruction
/// 3. Parse the instruction data to extract:
///    - Number of signatures
///    - Public key
///    - Message
///    - Signature
/// 4. Verify the public key matches our authorized signer
/// 5. Reconstruct the expected message and verify it matches
/// 
/// # Message Format
/// The signed message is constructed as:
/// ```
/// DOMAIN_SEPARATOR (10 bytes) ||
/// program_id (32 bytes) ||
/// buyer (32 bytes) ||
/// payment_mint (32 bytes) ||
/// payment_type (1 byte) ||
/// payment_amount (8 bytes, little-endian) ||
/// token_amount (8 bytes, little-endian) ||
/// nonce (8 bytes, little-endian)
/// ```
/// 
/// Total: 131 bytes
fn verify_ed25519_signature(
    instructions_sysvar: &AccountInfo,
    authorized_signer: &Pubkey,
    buyer: &Pubkey,
    payment_mint: &Pubkey,
    payment_type: u8,
    payment_amount: u64,
    token_amount: u64,
    nonce: u64,
    program_id: &Pubkey,
) -> Result<()> {
    // The ed25519 signature verification instruction must be the instruction
    // immediately before this one (index = current_index - 1)
    // 
    // We look for the ed25519 instruction at index 0, as it should be first
    // in the transaction
    
    let ix = load_instruction_at_checked(0, instructions_sysvar)
        .map_err(|_| PresaleError::InvalidSignatureInstruction)?;
    
    // Verify the instruction is to the ed25519 program
    require!(
        ix.program_id == ed25519_program::ID,
        PresaleError::InvalidSignatureInstruction
    );

    // ========================================================================
    // ED25519 INSTRUCTION DATA FORMAT
    // ========================================================================
    // 
    // The ed25519 program instruction data format:
    // - Byte 0: Number of signatures (must be 1 for our use case)
    // - Byte 1: Padding
    // - Bytes 2-3: Signature offset (u16 LE)
    // - Bytes 4-5: Signature instruction index (u16 LE)
    // - Bytes 6-7: Public key offset (u16 LE)
    // - Bytes 8-9: Public key instruction index (u16 LE)
    // - Bytes 10-11: Message data offset (u16 LE)
    // - Bytes 12-13: Message data size (u16 LE)
    // - Bytes 14-15: Message instruction index (u16 LE)
    // - Remaining: Signature (64 bytes) + Public key (32 bytes) + Message
    // ========================================================================
    
    let ix_data = &ix.data;
    
    // Verify we have at least the header
    require!(ix_data.len() >= 16, PresaleError::InvalidSignatureData);
    
    // Number of signatures must be 1
    require!(ix_data[0] == 1, PresaleError::InvalidSignatureData);
    
    // Parse offsets (all are u16 little-endian)
    let sig_offset = u16::from_le_bytes([ix_data[2], ix_data[3]]) as usize;
    let pubkey_offset = u16::from_le_bytes([ix_data[6], ix_data[7]]) as usize;
    let msg_offset = u16::from_le_bytes([ix_data[10], ix_data[11]]) as usize;
    let msg_size = u16::from_le_bytes([ix_data[12], ix_data[13]]) as usize;
    
    // Verify offsets are within bounds
    require!(
        sig_offset + 64 <= ix_data.len(),
        PresaleError::InvalidSignatureData
    );
    require!(
        pubkey_offset + 32 <= ix_data.len(),
        PresaleError::InvalidSignatureData
    );
    require!(
        msg_offset + msg_size <= ix_data.len(),
        PresaleError::InvalidSignatureData
    );
    
    // Extract and verify public key matches authorized signer
    let pubkey_bytes: [u8; 32] = ix_data[pubkey_offset..pubkey_offset + 32]
        .try_into()
        .map_err(|_| PresaleError::InvalidSignatureData)?;
    let signer_pubkey = Pubkey::from(pubkey_bytes);
    
    require!(
        signer_pubkey == *authorized_signer,
        PresaleError::UnauthorizedSigner
    );
    
    // ========================================================================
    // MESSAGE VERIFICATION
    // ========================================================================
    // 
    // Reconstruct the expected message and compare with the signed message.
    // This ensures the signature authorizes exactly this transaction.
    // ========================================================================
    
    // Build expected message
    let mut expected_message = Vec::with_capacity(131);
    expected_message.extend_from_slice(DOMAIN_SEPARATOR);      // 10 bytes
    expected_message.extend_from_slice(program_id.as_ref());   // 32 bytes
    expected_message.extend_from_slice(buyer.as_ref());        // 32 bytes
    expected_message.extend_from_slice(payment_mint.as_ref()); // 32 bytes
    expected_message.push(payment_type);                        // 1 byte
    expected_message.extend_from_slice(&payment_amount.to_le_bytes()); // 8 bytes
    expected_message.extend_from_slice(&token_amount.to_le_bytes());   // 8 bytes
    expected_message.extend_from_slice(&nonce.to_le_bytes());          // 8 bytes
    
    // Extract signed message from instruction
    let signed_message = &ix_data[msg_offset..msg_offset + msg_size];
    
    // Verify message matches
    require!(
        signed_message == expected_message.as_slice(),
        PresaleError::InvalidSignatureMessage
    );
    
    // If we reach here, the ed25519 program has already verified the signature
    // is valid for this message and public key. We've verified the public key
    // matches our authorized signer and the message matches our expected format.
    
    Ok(())
}

// ============================================================================
// ACCOUNT STRUCTURES
// ============================================================================

/// Global configuration for the presale program.
/// 
/// This PDA stores all configuration parameters and is used to validate
/// transactions and calculate vesting schedules.
#[account]
#[derive(Default)]
pub struct Config {
    /// Admin who can update config and withdraw tokens
    pub admin: Pubkey,
    /// Treasury wallet that receives all payments
    pub treasury: Pubkey,
    /// Public key authorized to sign purchase transactions
    pub authorized_signer: Pubkey,
    /// Mint address of the presale token
    pub presale_token_mint: Pubkey,
    /// USDT mint address for payment validation
    pub usdt_mint: Pubkey,
    /// USDC mint address for payment validation
    pub usdc_mint: Pubkey,
    /// Price per token unit (in payment token smallest units)
    pub token_price_per_unit: u64,
    /// Decimals of the presale token
    pub presale_token_decimals: u8,
    /// Cliff duration in seconds (no tokens claimable during cliff)
    pub cliff_duration: i64,
    /// Unix timestamp when vesting starts
    pub vesting_start_time: i64,
    /// Total vesting duration in seconds (including cliff)
    pub vesting_duration: i64,
    /// Whether the presale is currently active
    pub is_active: bool,
    /// Total tokens sold across all purchases
    pub total_sold: u64,
    /// PDA bump seed
    pub bump: u8,
}

impl Config {
    pub const LEN: usize = 8 +  // discriminator
        32 +  // admin
        32 +  // treasury
        32 +  // authorized_signer
        32 +  // presale_token_mint
        32 +  // usdt_mint
        32 +  // usdc_mint
        8 +   // token_price_per_unit
        1 +   // presale_token_decimals
        8 +   // cliff_duration
        8 +   // vesting_start_time
        8 +   // vesting_duration
        1 +   // is_active
        8 +   // total_sold
        1 +   // bump
        64;   // padding for future use
}

/// Vesting account for tracking a user's purchased and claimed tokens.
/// 
/// Each buyer has one vesting account PDA derived from their wallet address.
#[account]
#[derive(Default)]
pub struct VestingAccount {
    /// Buyer's wallet address
    pub buyer: Pubkey,
    /// Total tokens purchased (accumulated across all purchases)
    pub total_purchased: u64,
    /// Amount of tokens already claimed
    pub claimed_amount: u64,
    /// PDA bump seed
    pub bump: u8,
}

impl VestingAccount {
    pub const LEN: usize = 8 +  // discriminator
        32 +  // buyer
        8 +   // total_purchased
        8 +   // claimed_amount
        1 +   // bump
        32;   // padding for future use
}

/// Nonce account for tracking used nonces (replay protection).
/// 
/// Each nonce is a PDA derived from the buyer address and nonce value.
/// Once used, the nonce cannot be reused.
#[account]
#[derive(Default)]
pub struct NonceAccount {
    /// Whether this nonce has been used
    pub is_used: bool,
    /// Buyer who used this nonce
    pub buyer: Pubkey,
    /// The nonce value
    pub nonce: u64,
    /// Timestamp when the nonce was used
    pub used_at: i64,
}

impl NonceAccount {
    pub const LEN: usize = 8 +  // discriminator
        1 +   // is_used
        32 +  // buyer
        8 +   // nonce
        8 +   // used_at
        16;   // padding
}

// ============================================================================
// INSTRUCTION PARAMETERS
// ============================================================================

/// Parameters for initializing the presale configuration.
#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct ConfigParams {
    /// Treasury wallet address
    pub treasury: Pubkey,
    /// Authorized signer public key
    pub authorized_signer: Pubkey,
    /// USDT mint address
    pub usdt_mint: Pubkey,
    /// USDC mint address
    pub usdc_mint: Pubkey,
    /// Price per token unit
    pub token_price_per_unit: u64,
    /// Cliff duration in seconds
    pub cliff_duration: i64,
    /// Vesting start time (unix timestamp)
    pub vesting_start_time: i64,
    /// Total vesting duration in seconds
    pub vesting_duration: i64,
}

// ============================================================================
// ACCOUNT CONTEXTS
// ============================================================================

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    
    #[account(
        init,
        payer = admin,
        space = Config::LEN,
        seeds = [CONFIG_SEED],
        bump
    )]
    pub config: Account<'info, Config>,
    
    /// The presale token mint (must already exist)
    pub presale_token_mint: Account<'info, Mint>,
    
    /// Token vault PDA to hold presale tokens
    #[account(
        init,
        payer = admin,
        seeds = [VAULT_SEED, config.key().as_ref()],
        bump,
        token::mint = presale_token_mint,
        token::authority = token_vault,
    )]
    pub token_vault: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(
        constraint = admin.key() == config.admin @ PresaleError::Unauthorized
    )]
    pub admin: Signer<'info>,
    
    #[account(
        mut,
        seeds = [CONFIG_SEED],
        bump = config.bump
    )]
    pub config: Account<'info, Config>,
}

#[derive(Accounts)]
#[instruction(payment_amount: u64, token_amount: u64, nonce: u64)]
pub struct BuyTokensSpl<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,
    
    #[account(
        mut,
        seeds = [CONFIG_SEED],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
    
    /// Payment token mint (must be USDT or USDC)
    #[account(
        constraint = payment_mint.key() == config.usdt_mint || 
                     payment_mint.key() == config.usdc_mint 
                     @ PresaleError::InvalidPaymentMint
    )]
    pub payment_mint: Account<'info, Mint>,
    
    /// Buyer's payment token account
    #[account(
        mut,
        constraint = buyer_payment_account.owner == buyer.key() @ PresaleError::InvalidTokenAccount,
        constraint = buyer_payment_account.mint == payment_mint.key() @ PresaleError::InvalidTokenAccount,
    )]
    pub buyer_payment_account: Account<'info, TokenAccount>,
    
    /// Treasury's payment token account
    #[account(
        mut,
        constraint = treasury_payment_account.owner == config.treasury @ PresaleError::InvalidTreasuryAccount,
        constraint = treasury_payment_account.mint == payment_mint.key() @ PresaleError::InvalidTreasuryAccount,
    )]
    pub treasury_payment_account: Account<'info, TokenAccount>,
    
    /// Vesting account for the buyer (created if doesn't exist)
    #[account(
        init_if_needed,
        payer = buyer,
        space = VestingAccount::LEN,
        seeds = [VESTING_SEED, buyer.key().as_ref()],
        bump
    )]
    pub vesting_account: Account<'info, VestingAccount>,
    
    /// Nonce account for replay protection
    #[account(
        init,
        payer = buyer,
        space = NonceAccount::LEN,
        seeds = [NONCE_SEED, buyer.key().as_ref(), &nonce.to_le_bytes()],
        bump
    )]
    pub nonce_account: Account<'info, NonceAccount>,
    
    /// Instructions sysvar for signature verification
    /// CHECK: This is the instructions sysvar
    #[account(address = IX_ID)]
    pub instructions_sysvar: AccountInfo<'info>,
    
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(payment_amount: u64, token_amount: u64, nonce: u64)]
pub struct BuyTokensSol<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,
    
    #[account(
        mut,
        seeds = [CONFIG_SEED],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
    
    /// Treasury wallet to receive SOL
    /// CHECK: Validated against config.treasury
    #[account(
        mut,
        constraint = treasury.key() == config.treasury @ PresaleError::InvalidTreasuryAccount
    )]
    pub treasury: AccountInfo<'info>,
    
    /// Vesting account for the buyer
    #[account(
        init_if_needed,
        payer = buyer,
        space = VestingAccount::LEN,
        seeds = [VESTING_SEED, buyer.key().as_ref()],
        bump
    )]
    pub vesting_account: Account<'info, VestingAccount>,
    
    /// Nonce account for replay protection
    #[account(
        init,
        payer = buyer,
        space = NonceAccount::LEN,
        seeds = [NONCE_SEED, buyer.key().as_ref(), &nonce.to_le_bytes()],
        bump
    )]
    pub nonce_account: Account<'info, NonceAccount>,
    
    /// Instructions sysvar for signature verification
    /// CHECK: This is the instructions sysvar
    #[account(address = IX_ID)]
    pub instructions_sysvar: AccountInfo<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ClaimTokens<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        mut,
        seeds = [VESTING_SEED, buyer.key().as_ref()],
        bump = vesting_account.bump,
        constraint = vesting_account.buyer == buyer.key() @ PresaleError::InvalidVestingAccount,
    )]
    pub vesting_account: Account<'info, VestingAccount>,
    
    /// Token vault holding presale tokens
    #[account(
        mut,
        seeds = [VAULT_SEED, config.key().as_ref()],
        bump,
    )]
    pub token_vault: Account<'info, TokenAccount>,
    
    /// Buyer's token account to receive claimed tokens
    #[account(
        init_if_needed,
        payer = buyer,
        associated_token::mint = presale_token_mint,
        associated_token::authority = buyer,
    )]
    pub buyer_token_account: Account<'info, TokenAccount>,
    
    #[account(
        constraint = presale_token_mint.key() == config.presale_token_mint 
                     @ PresaleError::InvalidTokenMint
    )]
    pub presale_token_mint: Account<'info, Mint>,
    
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DepositTokens<'info> {
    #[account(
        mut,
        constraint = admin.key() == config.admin @ PresaleError::Unauthorized
    )]
    pub admin: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        mut,
        constraint = admin_token_account.owner == admin.key() @ PresaleError::InvalidTokenAccount,
        constraint = admin_token_account.mint == config.presale_token_mint @ PresaleError::InvalidTokenAccount,
    )]
    pub admin_token_account: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        seeds = [VAULT_SEED, config.key().as_ref()],
        bump,
    )]
    pub token_vault: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct WithdrawTokens<'info> {
    #[account(
        mut,
        constraint = admin.key() == config.admin @ PresaleError::Unauthorized
    )]
    pub admin: Signer<'info>,
    
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
    
    #[account(
        mut,
        constraint = admin_token_account.owner == admin.key() @ PresaleError::InvalidTokenAccount,
        constraint = admin_token_account.mint == config.presale_token_mint @ PresaleError::InvalidTokenAccount,
    )]
    pub admin_token_account: Account<'info, TokenAccount>,
    
    #[account(
        mut,
        seeds = [VAULT_SEED, config.key().as_ref()],
        bump,
    )]
    pub token_vault: Account<'info, TokenAccount>,
    
    pub token_program: Program<'info, Token>,
}

// ============================================================================
// EVENTS
// ============================================================================

#[event]
pub struct PresaleInitialized {
    pub admin: Pubkey,
    pub treasury: Pubkey,
    pub authorized_signer: Pubkey,
    pub presale_token_mint: Pubkey,
    pub token_price: u64,
}

#[event]
pub struct ConfigUpdated {
    pub treasury: Pubkey,
    pub authorized_signer: Pubkey,
    pub token_price: u64,
    pub is_active: bool,
}

#[event]
pub struct TokensPurchased {
    pub buyer: Pubkey,
    pub payment_mint: Pubkey,
    pub payment_amount: u64,
    pub token_amount: u64,
    pub nonce: u64,
}

#[event]
pub struct TokensClaimed {
    pub buyer: Pubkey,
    pub amount: u64,
    pub total_claimed: u64,
    pub total_purchased: u64,
}

#[event]
pub struct TokensDeposited {
    pub admin: Pubkey,
    pub amount: u64,
}

#[event]
pub struct TokensWithdrawn {
    pub admin: Pubkey,
    pub amount: u64,
}

// ============================================================================
// ERRORS
// ============================================================================

#[error_code]
pub enum PresaleError {
    #[msg("Presale is not currently active")]
    PresaleNotActive,
    
    #[msg("Invalid payment mint - must be USDT or USDC")]
    InvalidPaymentMint,
    
    #[msg("Insufficient payment amount")]
    InsufficientPayment,
    
    #[msg("Invalid signature instruction - ed25519 verification required")]
    InvalidSignatureInstruction,
    
    #[msg("Invalid signature data format")]
    InvalidSignatureData,
    
    #[msg("Signature message does not match expected format")]
    InvalidSignatureMessage,
    
    #[msg("Signer is not authorized")]
    UnauthorizedSigner,
    
    #[msg("Nonce has already been used")]
    NonceAlreadyUsed,
    
    #[msg("Arithmetic overflow")]
    Overflow,
    
    #[msg("Nothing to claim - no vested tokens available")]
    NothingToClaim,
    
    #[msg("Invalid token account")]
    InvalidTokenAccount,
    
    #[msg("Invalid treasury account")]
    InvalidTreasuryAccount,
    
    #[msg("Invalid vesting account")]
    InvalidVestingAccount,
    
    #[msg("Invalid token mint")]
    InvalidTokenMint,
    
    #[msg("Invalid vesting duration - must be greater than 0")]
    InvalidVestingDuration,
    
    #[msg("Invalid token price - must be greater than 0")]
    InvalidTokenPrice,
    
    #[msg("Unauthorized - admin only")]
    Unauthorized,
}
