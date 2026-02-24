use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};
use crate::state::*;
use crate::constants::*;
use crate::errors::PresaleError;

pub fn claim(ctx: Context<Claim>, _identity_key: [u8; 32]) -> Result<()> {
    let config = &ctx.accounts.config;
    require!(config.status == PresaleStatus::TokenLaunched, PresaleError::NotLaunched);

    let allocation = &mut ctx.accounts.user_allocation;
    require!(allocation.claim_authority != Pubkey::default(), PresaleError::ClaimAuthorityNotBound);
    require!(allocation.claim_authority == ctx.accounts.user.key(), PresaleError::ClaimAuthorityMismatch);

    // Apply any new global unlock of the vesting (non-TGE) portion
    if config.global_unlock_pct > allocation.last_unlock_pct {
        let new_pct = (config.global_unlock_pct - allocation.last_unlock_pct) as u64;
        let newly_unlocked = allocation.amount_vesting.checked_mul(new_pct).unwrap().checked_div(100).unwrap();
        allocation.claimable_amount = allocation.claimable_amount.checked_add(newly_unlocked).unwrap();
        allocation.last_unlock_pct = config.global_unlock_pct;
    }

    let amount_to_claim = allocation.claimable_amount;

    require!(amount_to_claim > 0, PresaleError::NothingToClaim);

    let seeds = &[
        SEED_VAULT,
        config.to_account_info().key.as_ref(),
        &[ctx.bumps.vault_token_account],
    ];
    let signer = &[&seeds[..]];

    let cpi_accounts = Transfer {
        from: ctx.accounts.vault_token_account.to_account_info(),
        to: ctx.accounts.user_token_account.to_account_info(),
        authority: ctx.accounts.vault_token_account.to_account_info(),
    };
    let cpi_program = ctx.accounts.token_program.to_account_info();
    let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
    token::transfer(cpi_ctx, amount_to_claim)?;

    allocation.claimable_amount = 0;
    allocation.amount_claimed += amount_to_claim;

    emit!(crate::ClaimEvent {
        user: ctx.accounts.user.key(),
        amount: amount_to_claim,
    });

    Ok(())
}

#[derive(Accounts)]
#[instruction(identity_key: [u8; 32])]
pub struct Claim<'info> {
    #[account(seeds = [SEED_CONFIG], bump = config.bump)]
    pub config: Account<'info, PresaleConfig>,
    #[account(
        mut,
        seeds = [SEED_ALLOCATION, identity_key.as_ref()],
        bump,
    )]
    pub user_allocation: Account<'info, UserAllocation>,
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(
        mut,
        seeds = [SEED_VAULT, config.key().as_ref()],
        bump,
    )]
    pub vault_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub user_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}
