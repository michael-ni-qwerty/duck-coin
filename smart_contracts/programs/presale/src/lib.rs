use anchor_lang::prelude::*;
use crate::instructions::*;
use crate::state::*;

pub mod constants;
pub mod errors;
pub mod instructions;
pub mod state;

declare_id!("9GprBhFEyLipafFmS75rta8HGZTU5WPZRG3tWGJDBrmC");

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
        identity_key: [u8; 32],
        token_amount: u64,
        usd_amount: u64,
        payment_id: String,
    ) -> Result<()> {
        instructions::credit_allocation(ctx, identity_key, token_amount, usd_amount, payment_id)
    }

    pub fn update_config(ctx: Context<UpdateConfig>, new_price: u64, new_tge: u8, new_daily_cap: u64) -> Result<()> {
        instructions::update_config(ctx, new_price, new_tge, new_daily_cap)
    }

    pub fn set_status(ctx: Context<UpdateConfig>, status: PresaleStatus) -> Result<()> {
        instructions::set_status(ctx, status)
    }

    pub fn bind_claim_wallet(
        ctx: Context<BindClaimWallet>,
        identity_key: [u8; 32],
        claim_authority: Pubkey,
    ) -> Result<()> {
        instructions::bind_claim_wallet(ctx, identity_key, claim_authority)
    }

    pub fn claim(ctx: Context<Claim>, identity_key: [u8; 32]) -> Result<()> {
        instructions::claim(ctx, identity_key)
    }

    pub fn set_unlock(ctx: Context<SetUnlock>, unlock_pct: u8) -> Result<()> {
        instructions::set_unlock(ctx, unlock_pct)
    }
}

#[event]
pub struct CreditEvent {
    pub identity_key: [u8; 32],
    pub token_amount: u64,
    pub usd_amount: u64,
    pub payment_id: String,
}

#[event]
pub struct ClaimWalletBoundEvent {
    pub identity_key: [u8; 32],
    pub claim_authority: Pubkey,
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
pub struct UnlockEvent {
    pub new_unlock_pct: u8,
}
