use anchor_lang::prelude::*;
use crate::state::*;
use crate::constants::*;
use crate::errors::PresaleError;

pub fn update_config(
    ctx: Context<UpdateConfig>,
    new_price: u64,
    new_tge: u8,
    new_daily_cap: u64,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    let daily_state = &mut ctx.accounts.daily_state;
    let clock = Clock::get()?;
    let current_day = (clock.unix_timestamp / 86400) as u64;

    // Force ability to update config only in new day
    require!(daily_state.current_day < current_day, PresaleError::UpdateConfigOnlyOnNewDay);

    // 1. Invariants: Price can only increase, TGE and daily cap can only decrease
    require!(new_price >= config.token_price_usd, PresaleError::PriceCannotDecrease);
    require!(new_tge <= config.tge_percentage, PresaleError::TgeCannotIncrease);
    require!(new_daily_cap <= config.daily_cap, PresaleError::DailyCapExceedsSupply);

    // 2. Handle daily cap reduction (Manual Burn)
    let burn_amount = config.daily_cap.checked_sub(config.sold_today).unwrap();
    config.total_burned = config.total_burned.checked_add(burn_amount).unwrap();
    config.daily_cap = new_daily_cap;

    // 3. Handle daily rollover burn (Unspent amount)
    let unspent = new_daily_cap.saturating_sub(daily_state.sold_today);
    config.total_burned = config.total_burned.checked_add(unspent).unwrap();
    
    daily_state.current_day = current_day;
    daily_state.sold_today = 0;

    config.token_price_usd = new_price;
    config.tge_percentage = new_tge;

    if new_daily_cap == 0 {
        config.status = PresaleStatus::PresaleEnded;
    }

    emit!(crate::ConfigUpdateEvent {
        new_price,
        new_tge,
        new_daily_cap,
    });

    Ok(())
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(mut, seeds = [SEED_CONFIG], bump = config.bump, constraint = config.admin == admin.key())]
    pub config: Account<'info, PresaleConfig>,
    #[account(mut, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    pub admin: Signer<'info>,
}
