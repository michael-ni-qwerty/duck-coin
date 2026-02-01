use anchor_lang::prelude::*;
use anchor_spl::token::Mint;
use crate::state::*;
use crate::constants::*;

pub fn initialize(
    ctx: Context<Initialize>,
    start_time: i64,
    usdc_mint: Pubkey,
    usdt_mint: Pubkey,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.admin = ctx.accounts.admin.key();
    config.token_mint = ctx.accounts.token_mint.key();
    config.usdc_mint = usdc_mint;
    config.usdt_mint = usdt_mint;
    config.token_price_usd = 5 * 10u64.pow(7); // 5 cents per token in US
    config.tge_percentage = 50;
    config.daily_cap = 30_000_000 * 10u64.pow(9);
    config.presale_supply = 2_400_000_000 * 10u64.pow(9);
    config.start_time = start_time;
    config.total_sold = 0;
    config.total_burned = 0;
    config.status = PresaleStatus::PresaleActive;
    config.total_raised_sol = 0;
    config.total_raised_usdc = 0;
    config.total_raised_usdt = 0;
    config.sold_today = 0;
    config.bump = ctx.bumps.config;

    let daily_state = &mut ctx.accounts.daily_state;
    let clock = Clock::get()?;
    daily_state.current_day = (clock.unix_timestamp / 86400) as u64;
    daily_state.sold_today = 0;

    // Initialize launchpool vault
    let launchpool_vault = &mut ctx.accounts.launchpool_vault;
    launchpool_vault.admin = ctx.accounts.admin.key();
    launchpool_vault.bump = ctx.bumps.launchpool_vault;

    Ok(())
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = admin, space = 8 + PresaleConfig::LEN, seeds = [SEED_CONFIG], bump)]
    pub config: Account<'info, PresaleConfig>,
    #[account(init, payer = admin, space = 8 + DailyState::LEN, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    #[account(init, payer = admin, space = 8 + LaunchpoolVault::LEN, seeds = [SEED_LAUNCHPOOL], bump)]
    pub launchpool_vault: Account<'info, LaunchpoolVault>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub token_mint: Account<'info, Mint>,
    pub system_program: Program<'info, System>,
}
