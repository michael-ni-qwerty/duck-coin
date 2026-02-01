use anchor_lang::prelude::*;

#[account]
pub struct PresaleConfig {
    pub admin: Pubkey,
    pub token_mint: Pubkey,
    pub usdc_mint: Pubkey,
    pub usdt_mint: Pubkey,
    pub token_price_usd: u64,
    pub tge_percentage: u8,
    pub start_time: i64,
    pub daily_cap: u64,
    pub total_sold: u64,
    pub presale_supply: u64,
    pub total_burned: u64,
    pub status: PresaleStatus,
    pub total_raised_sol: u64,
    pub total_raised_usdc: u64,
    pub total_raised_usdt: u64,
    pub sold_today: u64,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum PresaleStatus {
    PresaleActive,
    PresaleEnded,
    TokenLaunched,
}

impl PresaleConfig {
    pub const LEN: usize = 32 + 32 + 32 + 32 + 8 + 1 + 8 + 8 + 8 + 8 + 8 + 1 + 8 + 8 + 8 + 8 + 1;
}

#[account]
pub struct DailyState {
    pub current_day: u64,
    pub sold_today: u64,
}

impl DailyState {
    pub const LEN: usize = 8 + 8;
}

#[account]
pub struct NonceAccount {
    pub nonce: u64,
}

impl NonceAccount {
    pub const LEN: usize = 8;
}

#[account]
pub struct LaunchpoolVault {
    pub admin: Pubkey,
    pub bump: u8,
}

impl LaunchpoolVault {
    pub const LEN: usize = 32 + 1;
}

#[account]
pub struct UserAllocation {
    pub amount_purchased: u64,
    pub amount_claimed: u64,
    pub claimable_amount: u64,
}

impl UserAllocation {
    pub const LEN: usize = 8 + 8 + 8;
}
