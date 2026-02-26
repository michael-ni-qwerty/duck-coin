use anchor_lang::prelude::*;
use anchor_spl::token::{self, Burn, Mint, Token, TokenAccount};
use crate::state::*;
use crate::constants::*;
// use crate::errors::PresaleError;

pub fn update_config(
    ctx: Context<UpdateConfig>,
    new_price: u64,
    new_tge: u8,
    new_daily_cap: u64,
    // TODO: delete this after testing
    new_start_time: i64,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    let daily_state = &mut ctx.accounts.daily_state;
    let clock = Clock::get()?;
    let current_day = (clock.unix_timestamp / 86400) as u64;

    // TODO: delete this after testing
    config.start_time = new_start_time;

    // Force ability to update config only in new day
    // require!(daily_state.current_day < current_day, PresaleError::UpdateConfigOnlyOnNewDay);

    // 1. Invariants: Price can only increase, TGE and daily cap can only decrease
    // require!(new_price >= config.token_price_usd, PresaleError::PriceCannotDecrease);
    // require!(new_tge <= config.tge_percentage, PresaleError::TgeCannotIncrease);
    // require!(new_daily_cap <= config.daily_cap, PresaleError::DailyCapExceedsSupply);

    // Calculate total burn amount
    let mut total_burn_amount: u64 = 0;

    // 2. Handle daily cap reduction (Manual Burn)
    let burn_amount = config.daily_cap.checked_sub(config.sold_today).unwrap();
    total_burn_amount = total_burn_amount.checked_add(burn_amount).unwrap();
    config.daily_cap = new_daily_cap;

    // 3. Handle daily rollover burn (Unspent amount)
    let unspent = new_daily_cap.saturating_sub(daily_state.sold_today);
    total_burn_amount = total_burn_amount.checked_add(unspent).unwrap();
    
    // Perform actual on-chain burn if there are tokens to burn
    if total_burn_amount > 0 {
        config.total_burned = config.total_burned.checked_add(total_burn_amount).unwrap();
        
        burn_tokens(
            total_burn_amount,
            config.to_account_info().key.as_ref(),
            ctx.bumps.vault_token_account,
            ctx.accounts.token_mint.to_account_info(),
            ctx.accounts.vault_token_account.to_account_info(),
            ctx.accounts.token_program.to_account_info(),
        )?;
    }
    
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

fn burn_tokens<'info>(
    amount: u64,
    config_key: &[u8],
    vault_bump: u8,
    mint: AccountInfo<'info>,
    vault: AccountInfo<'info>,
    token_program: AccountInfo<'info>,
) -> Result<()> {
    let seeds = &[
        SEED_VAULT,
        config_key,
        &[vault_bump],
    ];
    let signer = &[&seeds[..]];

    let cpi_accounts = Burn {
        mint,
        from: vault.clone(),
        authority: vault,
    };
    
    let cpi_ctx = CpiContext::new_with_signer(token_program, cpi_accounts, signer);
    token::burn(cpi_ctx, amount)
}

#[derive(Accounts)]
pub struct UpdateConfig<'info> {
    #[account(mut, seeds = [SEED_CONFIG], bump = config.bump, constraint = config.admin == admin.key())]
    pub config: Account<'info, PresaleConfig>,
    #[account(mut, seeds = [SEED_DAILY_STATE], bump)]
    pub daily_state: Account<'info, DailyState>,
    #[account(mut)]
    pub admin: Signer<'info>,
    
    // Accounts needed for burning
    #[account(mut)]
    pub token_mint: Account<'info, Mint>,
    #[account(
        mut,
        seeds = [SEED_VAULT, config.key().as_ref()],
        bump,
    )]
    pub vault_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}
