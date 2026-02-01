use anchor_lang::prelude::*;

#[error_code]
pub enum PresaleError {
    #[msg("Daily sale cap exceeded")]
    DailyCapExceeded,
    #[msg("Daily cap cannot exceed current daily cap")]
    DailyCapExceedsSupply,
    #[msg("Price can only increase")]
    PriceCannotDecrease,
    #[msg("TGE percentage can only decrease")]
    TgeCannotIncrease,
    #[msg("Presale has not started")]
    PresaleNotStarted,
    #[msg("Nothing to claim")]
    NothingToClaim,
    #[msg("Presale is not active")]
    PresaleNotActive,
    #[msg("Presale has not launched")]
    NotLaunched,
    #[msg("Cannot reopen presale")]
    CannotReopenPresale,
    #[msg("Presale supply exceeded")]
    SupplyExceeded,
    #[msg("Supply can only decrease")]
    SupplyCannotIncrease,
    #[msg("Supply cannot be lower than total tokens already sold")]
    SupplyBelowTotalSold,
    #[msg("Backend authorization message expired")]
    MessageExpired,
    #[msg("Invalid backend public key")]
    InvalidBackendKey,
    #[msg("Invalid backend signature")]
    InvalidSignature,
    #[msg("Invalid authorization message")]
    InvalidAuthMessage,
    #[msg("Missing Ed25519 verification instruction")]
    InvalidEd25519Program,
    #[msg("Config can only be updated once per day (on a new day)")]
    UpdateConfigOnlyOnNewDay,
    #[msg("Presale has not ended yet")]
    PresaleNotEnded,
    #[msg("Invalid oracle price")]
    InvalidPrice,
}
