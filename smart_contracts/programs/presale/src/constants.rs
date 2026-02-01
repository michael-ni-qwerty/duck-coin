use anchor_lang::prelude::*;

#[constant]
pub const SEED_CONFIG: &[u8] = b"config";
#[constant]
pub const SEED_DAILY_STATE: &[u8] = b"daily_state";
#[constant]
pub const SEED_ALLOCATION: &[u8] = b"allocation";
#[constant]
pub const SEED_NONCE: &[u8] = b"nonce";
#[constant]
pub const SEED_VAULT: &[u8] = b"vault";
#[constant]
pub const SEED_LAUNCHPOOL: &[u8] = b"launchpool";

pub const BACKEND_PUBKEY: [u8; 32] = [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
];
