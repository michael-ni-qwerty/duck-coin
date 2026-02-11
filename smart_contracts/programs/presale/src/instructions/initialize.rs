use anchor_lang::prelude::*;
use crate::state::*;
use crate::constants::*;

pub fn initialize(
    ctx: Context<Initialize>,
    start_time: i64,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.admin = ctx.accounts.admin.key();
    config.token_mint = ctx.accounts.token_mint.key();
    config.token_price_usd = 5 * 10u64.pow(7); // 5 cents per token in USD
    config.tge_percentage = 50;
    config.daily_cap = 30_000_000 * 10u64.pow(9);
    config.presale_supply = 2_400_000_000 * 10u64.pow(9);
    config.start_time = start_time;
    config.total_sold = 0;
    config.total_burned = 0;
    config.status = PresaleStatus::PresaleActive;
    config.total_raised_usd = 0;
    config.sold_today = 0;
    config.bump = ctx.bumps.config;

    let daily_state = &mut ctx.accounts.daily_state;
    let clock = Clock::get()?;
    daily_state.current_day = (clock.unix_timestamp / 86400) as u64;
    daily_state.sold_today = 0;

    Ok(())
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = admin, space = 8 + PresaleConfig::LEN, seeds = [SEED_CONFIG], bump)]
    pub config: Account<'info, PresaleConfig>,
    #[account(init, payer = admin, space = 8 + DailyState::LEN, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    #[account(mut)]
    pub admin: Signer<'info>,
    /// CHECK: Token mint for the presale token (stored in config for reference)
    pub token_mint: AccountInfo<'info>,
    pub system_program: Program<'info, System>,
}
