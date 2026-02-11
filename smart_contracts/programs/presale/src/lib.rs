use anchor_lang::prelude::*;
use crate::instructions::*;
use crate::state::*;

pub mod constants;
pub mod errors;
pub mod instructions;
pub mod state;

declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

#[program]
pub mod presale {
    use super::*;

    pub fn initialize(
        ctx: Context<Initialize>,
        start_time: i64,
    ) -> Result<()> {
        instructions::initialize(ctx, start_time)
    }

    pub fn credit_allocation(
        ctx: Context<CreditAllocation>,
        user: Pubkey,
        token_amount: u64,
        usd_amount: u64,
        payment_id: String,
    ) -> Result<()> {
        instructions::credit_allocation(ctx, user, token_amount, usd_amount, payment_id)
    }

    pub fn update_config(ctx: Context<UpdateConfig>, new_price: u64, new_tge: u8, new_daily_cap: u64) -> Result<()> {
        instructions::update_config(ctx, new_price, new_tge, new_daily_cap)
    }

    pub fn set_status(ctx: Context<UpdateConfig>, status: PresaleStatus) -> Result<()> {
        instructions::set_status(ctx, status)
    }

    pub fn claim(ctx: Context<Claim>) -> Result<()> {
        instructions::claim(ctx)
    }
}

#[event]
pub struct CreditEvent {
    pub user: Pubkey,
    pub token_amount: u64,
    pub usd_amount: u64,
    pub payment_id: String,
}

#[event]
pub struct ClaimEvent {
    pub user: Pubkey,
    pub amount: u64,
}

#[event]
pub struct ConfigUpdateEvent {
    pub new_price: u64,
    pub new_tge: u8,
    pub new_daily_cap: u64,
}
