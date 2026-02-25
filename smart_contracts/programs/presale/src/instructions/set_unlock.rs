use anchor_lang::prelude::*;
use crate::state::*;
use crate::constants::*;
// use crate::errors::PresaleError;

pub fn set_unlock(ctx: Context<SetUnlock>, unlock_pct: u8) -> Result<()> {
    let config = &mut ctx.accounts.config;

    // require!(unlock_pct <= 100, PresaleError::UnlockExceedsMax);
    // require!(unlock_pct >= config.global_unlock_pct, PresaleError::UnlockCannotDecrease);

    config.global_unlock_pct = unlock_pct;

    emit!(crate::UnlockEvent {
        new_unlock_pct: unlock_pct,
    });

    Ok(())
}

#[derive(Accounts)]
pub struct SetUnlock<'info> {
    #[account(mut, seeds = [SEED_CONFIG], bump = config.bump, constraint = config.admin == admin.key())]
    pub config: Account<'info, PresaleConfig>,
    pub admin: Signer<'info>,
}
