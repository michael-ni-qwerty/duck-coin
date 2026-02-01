use anchor_lang::prelude::*;
use pyth_sdk_solana::state::SolanaPriceAccount;
use std::str::FromStr;
use crate::state::*;
use crate::constants::*;
use crate::errors::PresaleError;
use crate::instructions::utils::verify_ed25519_signature;

pub fn buy_sol(ctx: Context<BuySol>, lamports: u64, expires_at: i64, signature: [u8; 64]) -> Result<()> {
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
    message.extend_from_slice(b"BUY_SOL_"); 
    message.extend_from_slice(&ctx.accounts.user_nonce.nonce.to_le_bytes());
    message.extend_from_slice(&expires_at.to_le_bytes());

    verify_ed25519_signature(
        &ctx.accounts.instructions_sysvar,
        &BACKEND_PUBKEY,
        &message,
        &signature,
    )?;

    // 5. Increment Nonce (Replay Protection)
    ctx.accounts.user_nonce.nonce += 1;

    // 6. Price calculation using Pyth oracle
    let sol_price_account = ctx.accounts.sol_price_feed.to_account_info();
    let price_feed = SolanaPriceAccount::account_info_to_feed(&sol_price_account)
        .map_err(|_| PresaleError::InvalidPrice)?;
    let sol_price = price_feed.get_price_no_older_than(clock.unix_timestamp, 60)
        .ok_or(PresaleError::InvalidPrice)?;
    require!(sol_price.price > 0, PresaleError::InvalidPrice);
    
    let sol_price_usd = if sol_price.expo >= 0 {
        (sol_price.price as u128) * 10u128.pow(sol_price.expo as u32)
    } else {
        (sol_price.price as u128) / 10u128.pow((-sol_price.expo) as u32)
    };
    
    // Convert lamports to USD value, then to tokens
    let usd_value = (lamports as u128 * sol_price_usd) / 10u128.pow(9); // lamports are 9 decimals
    let token_amount = (usd_value * 10u128.pow(9)) / ctx.accounts.config.token_price_usd as u128;
    let token_amount_u64 = token_amount as u64;

    require!(ctx.accounts.daily_state.sold_today + token_amount_u64 <= ctx.accounts.config.daily_cap, PresaleError::DailyCapExceeded);
    require!(ctx.accounts.config.total_sold + token_amount_u64 <= ctx.accounts.config.presale_supply, PresaleError::SupplyExceeded);

    // 7. Transfer SOL to launchpool vault
    let ix = anchor_lang::solana_program::system_instruction::transfer(
        &ctx.accounts.user.key(),
        &ctx.accounts.launchpool_vault.to_account_info().key(),
        lamports,
    );
    anchor_lang::solana_program::program::invoke(
        &ix,
        &[
            ctx.accounts.user.to_account_info(),
            ctx.accounts.launchpool_vault.to_account_info(),
        ],
    )?;

    // 8. Update state
    let allocation = &mut ctx.accounts.user_allocation;
    allocation.amount_purchased += token_amount_u64;
    
    // Calculate and update claimable amount based on TGE percentage
    let tge_claimable = (token_amount_u64 * ctx.accounts.config.tge_percentage as u64) / 100;
    allocation.claimable_amount += tge_claimable;
    
    ctx.accounts.daily_state.sold_today += token_amount_u64;
    
    let config = &mut ctx.accounts.config;
    config.total_sold += token_amount_u64;
    config.total_raised_sol += lamports;

    emit!(crate::BuyEvent {
        buyer: ctx.accounts.user.key(),
        payment_amount: lamports,
        token_amount: token_amount_u64,
        payment_mint: Pubkey::default(),
    });

    Ok(())
}

#[derive(Accounts)]
pub struct BuySol<'info> {
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
    /// CHECK: Pyth SOL/USD price feed account
    #[account(constraint = sol_price_feed.key() == Pubkey::from_str("H6ARzDJwhJiCqy9sJfqKhMCH2RKM9nEYYGNGhLVK8t4b").unwrap())]
    pub sol_price_feed: AccountInfo<'info>,
    /// CHECK: Instructions sysvar
    #[account(address = anchor_lang::solana_program::sysvar::instructions::ID)]
    pub instructions_sysvar: AccountInfo<'info>,
    pub system_program: Program<'info, System>,
}
