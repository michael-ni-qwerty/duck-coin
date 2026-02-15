use anchor_lang::prelude::*;

#[account]
pub struct PresaleConfig {
    pub admin: Pubkey,
    pub token_mint: Pubkey,
    pub token_price_usd: u64,
    pub tge_percentage: u8,
    pub start_time: i64,
    pub daily_cap: u64,
    pub total_sold: u64,
    pub presale_supply: u64,
    pub total_burned: u64,
    pub status: PresaleStatus,
    pub total_raised_usd: u64,
    pub sold_today: u64,
    pub global_unlock_pct: u8,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq)]
pub enum PresaleStatus {
    PresaleActive,
    PresaleEnded,
    TokenLaunched,
}

impl PresaleConfig {
    // admin(32) + token_mint(32) + token_price_usd(8) + tge_percentage(1) + start_time(8)
    // + daily_cap(8) + total_sold(8) + presale_supply(8) + total_burned(8) + status(1)
    // + total_raised_usd(8) + sold_today(8) + global_unlock_pct(1) + bump(1)
    pub const LEN: usize = 32 + 32 + 8 + 1 + 8 + 8 + 8 + 8 + 8 + 1 + 8 + 8 + 1 + 1;
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
pub struct UserAllocation {
    pub amount_purchased: u64,
    pub amount_claimed: u64,
    pub claimable_amount: u64,
    pub amount_vesting: u64,
    pub last_unlock_pct: u8,
}

impl UserAllocation {
    // amount_purchased(8) + amount_claimed(8) + claimable_amount(8)
    // + amount_vesting(8) + last_unlock_pct(1)
    pub const LEN: usize = 8 + 8 + 8 + 8 + 1;
}
