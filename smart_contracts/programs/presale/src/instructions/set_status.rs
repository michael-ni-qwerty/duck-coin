use anchor_lang::prelude::*;
use crate::state::*;
use crate::errors::PresaleError;
use crate::instructions::update_config::UpdateConfig;

pub fn set_status(ctx: Context<UpdateConfig>, status: PresaleStatus) -> Result<()> {
    let config = &mut ctx.accounts.config;
    
    // Admin cannot reopen presale once ended or launched
    if config.status != PresaleStatus::PresaleActive {
        require!(status == PresaleStatus::TokenLaunched, PresaleError::CannotReopenPresale);
    }

    config.status = status;
    Ok(())
}
