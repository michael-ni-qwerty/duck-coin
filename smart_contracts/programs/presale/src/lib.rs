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
        usdc_mint: Pubkey,
        usdt_mint: Pubkey,
    ) -> Result<()> {
        instructions::initialize(ctx, start_time, usdc_mint, usdt_mint)
    }

    pub fn buy_sol(ctx: Context<BuySol>, lamports: u64, expires_at: i64, signature: [u8; 64]) -> Result<()> {
        instructions::buy_sol(ctx, lamports, expires_at, signature)
    }

    pub fn buy_spl(ctx: Context<BuySpl>, amount: u64, expires_at: i64, signature: [u8; 64]) -> Result<()> {
        instructions::buy_spl(ctx, amount, expires_at, signature)
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
pub struct BuyEvent {
    pub buyer: Pubkey,
    pub payment_amount: u64,
    pub token_amount: u64,
    pub payment_mint: Pubkey,
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

#[event]
pub struct LiquidityProvidedEvent {
    pub tick_lower: i32,
    pub tick_upper: i32,
    pub token_amount: u64,
}
