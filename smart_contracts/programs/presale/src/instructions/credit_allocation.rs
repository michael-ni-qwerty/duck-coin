use anchor_lang::prelude::*;
use crate::state::*;
use crate::constants::*;
use crate::errors::PresaleError;

pub fn credit_allocation(
    ctx: Context<CreditAllocation>,
    user: Pubkey,
    token_amount: u64,
    usd_amount: u64,
    payment_id: String,
) -> Result<()> {
    let clock = Clock::get()?;
    let config = &mut ctx.accounts.config;

    // 1. Check presale status and timing
    require!(config.status == PresaleStatus::PresaleActive, PresaleError::PresaleNotActive);
    require!(clock.unix_timestamp >= config.start_time, PresaleError::PresaleNotStarted);

    // 2. Check daily cap
    let current_day = (clock.unix_timestamp / 86400) as u64;
    require!(ctx.accounts.daily_state.current_day == current_day, PresaleError::UpdateConfigOnlyOnNewDay);
    require!(ctx.accounts.daily_state.sold_today + token_amount <= config.daily_cap, PresaleError::DailyCapExceeded);

    // 3. Check supply
    require!(config.total_sold + token_amount <= config.presale_supply, PresaleError::SupplyExceeded);

    // 4. Update user allocation
    let allocation = &mut ctx.accounts.user_allocation;
    allocation.amount_purchased += token_amount;

    // Calculate and update claimable amount based on TGE percentage
    let tge_claimable = (token_amount * config.tge_percentage as u64) / 100;
    allocation.claimable_amount += tge_claimable;

    // 5. Update global state
    ctx.accounts.daily_state.sold_today += token_amount;
    config.total_sold += token_amount;
    config.total_raised_usd += usd_amount;

    emit!(crate::CreditEvent {
        user,
        token_amount,
        usd_amount,
        payment_id,
    });

    Ok(())
}

#[derive(Accounts)]
#[instruction(user: Pubkey)]
pub struct CreditAllocation<'info> {
    #[account(mut, seeds = [SEED_CONFIG], bump = config.bump, constraint = config.admin == admin.key())]
    pub config: Account<'info, PresaleConfig>,
    #[account(mut, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    #[account(
        init_if_needed,
        payer = admin,
        space = 8 + UserAllocation::LEN,
        seeds = [SEED_ALLOCATION, user.as_ref()],
        bump
    )]
    pub user_allocation: Account<'info, UserAllocation>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}
