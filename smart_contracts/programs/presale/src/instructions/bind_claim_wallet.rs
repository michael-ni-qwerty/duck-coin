use anchor_lang::prelude::*;

use crate::constants::*;
use crate::errors::PresaleError;
use crate::state::*;

pub fn bind_claim_wallet(
    ctx: Context<BindClaimWallet>,
    identity_key: [u8; 32],
    claim_authority: Pubkey,
) -> Result<()> {
    let allocation = &mut ctx.accounts.user_allocation;
    require!(allocation.amount_purchased > 0, PresaleError::NothingToClaim);
    require!(claim_authority != Pubkey::default(), PresaleError::ClaimAuthorityNotBound);

    if allocation.claim_authority == Pubkey::default() {
        allocation.claim_authority = claim_authority;
    } else {
        require!(
            allocation.claim_authority == claim_authority,
            PresaleError::ClaimAuthorityAlreadyBound
        );
    }

    emit!(crate::ClaimWalletBoundEvent {
        identity_key,
        claim_authority,
    });

    Ok(())
}

#[derive(Accounts)]
#[instruction(identity_key: [u8; 32], _claim_authority: Pubkey)]
pub struct BindClaimWallet<'info> {
    #[account(seeds = [SEED_CONFIG], bump = config.bump, constraint = config.admin == admin.key())]
    pub config: Account<'info, PresaleConfig>,
    #[account(
        mut,
        seeds = [SEED_ALLOCATION, identity_key.as_ref()],
        bump,
    )]
    pub user_allocation: Account<'info, UserAllocation>,
    pub admin: Signer<'info>,
}
