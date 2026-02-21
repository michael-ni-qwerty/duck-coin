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
    require!(ctx.accounts.daily_state.sold_today.checked_add(token_amount).unwrap() <= config.daily_cap, PresaleError::DailyCapExceeded);

    // 3. Check supply
    require!(config.total_sold.checked_add(token_amount).unwrap() <= config.presale_supply, PresaleError::SupplyExceeded);

    // 4. Update user allocation
    let allocation = &mut ctx.accounts.user_allocation;
    allocation.amount_purchased = allocation.amount_purchased.checked_add(token_amount).unwrap();

    // TGE portion → immediately claimable after token launch
    let tge_claimable = token_amount.checked_mul(config.tge_percentage as u64).unwrap().checked_div(100).unwrap();
    allocation.claimable_amount = allocation.claimable_amount.checked_add(tge_claimable).unwrap();

    // Remaining portion → locked, released via admin global unlock
    let vesting_amount = token_amount - tge_claimable;
    allocation.amount_vesting = allocation.amount_vesting.checked_add(vesting_amount).unwrap();

    // 5. Update global state
    ctx.accounts.daily_state.sold_today = ctx.accounts.daily_state.sold_today.checked_add(token_amount).unwrap();
    config.total_sold = config.total_sold.checked_add(token_amount).unwrap();
    config.total_raised_usd = config.total_raised_usd.checked_add(usd_amount).unwrap();

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
