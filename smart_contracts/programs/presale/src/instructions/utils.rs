use anchor_lang::prelude::*;
use anchor_lang::solana_program::sysvar::instructions as instructions_sysvar;
use anchor_lang::solana_program::ed25519_program::ID as ED25519_ID;
use crate::errors::PresaleError;

pub fn verify_ed25519_signature(
    instructions_sysvar: &AccountInfo,
    expected_pubkey: &[u8; 32],
    expected_message: &[u8],
    expected_signature: &[u8; 64],
) -> Result<()> {
    let instruction_data = instructions_sysvar::load_instruction_at_checked(0, instructions_sysvar)?;

    if instruction_data.program_id != ED25519_ID {
        return Err(PresaleError::InvalidEd25519Program.into());
    }

    let mut current = 2;
    let sig_offset = u16::from_le_bytes([instruction_data.data[current], instruction_data.data[current+1]]) as usize;
    current += 4;
    let pubkey_offset = u16::from_le_bytes([instruction_data.data[current], instruction_data.data[current+1]]) as usize;
    current += 4;
    let msg_offset = u16::from_le_bytes([instruction_data.data[current], instruction_data.data[current+1]]) as usize;
    let msg_size = u16::from_le_bytes([instruction_data.data[current+2], instruction_data.data[current+3]]) as usize;

    let pubkey = &instruction_data.data[pubkey_offset..pubkey_offset + 32];
    if pubkey != expected_pubkey {
        return Err(PresaleError::InvalidBackendKey.into());
    }

    let sig = &instruction_data.data[sig_offset..sig_offset + 64];
    if sig != expected_signature {
        return Err(PresaleError::InvalidSignature.into());
    }

    let msg = &instruction_data.data[msg_offset..msg_offset + msg_size];
    if msg != expected_message {
        return Err(PresaleError::InvalidAuthMessage.into());
    }

    Ok(())
}
