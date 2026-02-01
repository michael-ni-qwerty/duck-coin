use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};
use crate::state::*;
use crate::constants::*;
use crate::errors::PresaleError;
use crate::instructions::utils::verify_ed25519_signature;

pub fn buy_spl(
    ctx: Context<BuySpl>, 
    amount: u64, 
    expires_at: i64, 
    signature: [u8; 64]
) -> Result<()> {
    let clock = Clock::get()?;
    
    // 1. Expiration check
    require!(clock.unix_timestamp <= expires_at, PresaleError::MessageExpired);

    // 2. Check presale status and timing
    require!(ctx.accounts.config.status == PresaleStatus::PresaleActive, PresaleError::PresaleNotActive);
    require!(clock.unix_timestamp >= ctx.accounts.config.start_time, PresaleError::PresaleNotStarted);

    // 3. Check if daily cap is available (daily rollover must be handled by update_config)
    let current_day = (clock.unix_timestamp / 86400) as u64;
    require!(ctx.accounts.daily_state.current_day == current_day, PresaleError::UpdateConfigOnlyOnNewDay);

    // 4. Ed25519 signature verification
    let mut message = Vec::with_capacity(88);
    message.extend_from_slice(ctx.program_id.as_ref());
    message.extend_from_slice(ctx.accounts.user.key().as_ref());
    message.extend_from_slice(b"BUY_SPL_"); 
    message.extend_from_slice(&ctx.accounts.user_nonce.nonce.to_le_bytes());
    message.extend_from_slice(&expires_at.to_le_bytes());

    verify_ed25519_signature(
        &ctx.accounts.instructions_sysvar,
        &BACKEND_PUBKEY,
        &message,
        &signature,
    )?;

    // 5. Increment Nonce
    ctx.accounts.user_nonce.nonce += 1;

    // 6. Price calculation
    let decimals = ctx.accounts.payment_mint.decimals;
    let normalized_payment = (amount as u128 * 10u128.pow(9)) / 10u128.pow(decimals as u32);
    let token_amount = (normalized_payment * 10u128.pow(6)) / ctx.accounts.config.token_price_usd as u128;
    let token_amount_u64 = token_amount as u64;

    require!(ctx.accounts.daily_state.sold_today + token_amount_u64 <= ctx.accounts.config.daily_cap, PresaleError::DailyCapExceeded);
    require!(ctx.accounts.config.total_sold + token_amount_u64 <= ctx.accounts.config.presale_supply, PresaleError::SupplyExceeded);

    // 7. Transfer SPL to launchpool vault
    let cpi_accounts = Transfer {
        from: ctx.accounts.user_token_account.to_account_info(),
        to: ctx.accounts.launchpool_vault_token_account.to_account_info(),
        authority: ctx.accounts.user.to_account_info(),
    };
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
    token::transfer(cpi_ctx, amount)?;

    // 8. Update state
    let allocation = &mut ctx.accounts.user_allocation;
    allocation.amount_purchased += token_amount_u64;
    
    // Calculate and update claimable amount based on TGE percentage
    let tge_claimable = (token_amount_u64 * ctx.accounts.config.tge_percentage as u64) / 100;
    allocation.claimable_amount += tge_claimable;
    
    ctx.accounts.daily_state.sold_today += token_amount_u64;
    
    let config = &mut ctx.accounts.config;
    config.total_sold += token_amount_u64;
    
    // Track per asset
    let mint = ctx.accounts.payment_mint.key();
    if mint == config.usdc_mint {
        config.total_raised_usdc += amount;
    } else if mint == config.usdt_mint {
        config.total_raised_usdt += amount;
    }

    emit!(crate::BuyEvent {
        buyer: ctx.accounts.user.key(),
        payment_amount: amount,
        token_amount: token_amount_u64,
        payment_mint: ctx.accounts.payment_mint.key(),
    });

    Ok(())
}

#[derive(Accounts)]
pub struct BuySpl<'info> {
    #[account(mut, seeds = [SEED_CONFIG], bump = config.bump)]
    pub config: Account<'info, PresaleConfig>,
    #[account(mut, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    #[account(
        init_if_needed,
        payer = user,
        space = 8 + UserAllocation::LEN,
        seeds = [SEED_ALLOCATION, user.key().as_ref()],
        bump
    )]
    pub user_allocation: Account<'info, UserAllocation>,
    #[account(
        init_if_needed,
        payer = user,
        space = 8 + NonceAccount::LEN,
        seeds = [SEED_NONCE, user.key().as_ref()],
        bump
    )]
    pub user_nonce: Account<'info, NonceAccount>,
    #[account(mut, seeds = [SEED_LAUNCHPOOL], bump = launchpool_vault.bump)]
    pub launchpool_vault: Account<'info, LaunchpoolVault>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub payment_mint: Account<'info, Mint>,
    #[account(mut)]
    pub user_token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        seeds = [SEED_LAUNCHPOOL, payment_mint.key().as_ref()],
        bump,
        token::mint = payment_mint,
        token::authority = launchpool_vault
    )]
    pub launchpool_vault_token_account: Account<'info, TokenAccount>,
    /// CHECK: Instructions sysvar
    #[account(address = anchor_lang::solana_program::sysvar::instructions::ID)]
    pub instructions_sysvar: AccountInfo<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}
