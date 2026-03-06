import logging
from fastapi import APIRouter, HTTPException, status

from app.models.presale import Investor
from app.schemas.presale import (
    ReferralStatsResponse,
    AttachReferralRequest,
    AttachReferralResponse,
)
from app.core.utils import scale_from_chain
from .common import validate_wallet_address

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/attach",
    response_model=AttachReferralResponse,
    summary="Attach a referral code to a wallet",
)
async def attach_referral(request: AttachReferralRequest) -> AttachReferralResponse:
    if not validate_wallet_address(request.wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format.",
        )

    # Find the referrer
    referrer = await Investor.get_or_none(referral_code=request.referral_code)
    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral code not found.",
        )

    # Check for self-referral
    if referrer.wallet_address.lower() == request.wallet_address.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use your own referral code.",
        )

    # Find or create the investor
    investor, created = await Investor.get_or_create(
        wallet_address=request.wallet_address.lower()
    )

    # If already attached, return existing (idempotent)
    if investor.referred_by:
        return AttachReferralResponse(
            message="Referral already attached.",
            wallet_address=investor.wallet_address,
            referred_by=investor.referred_by,
        )

    # Attach the referral
    investor.referred_by = referrer.wallet_address
    await investor.save(update_fields=["referred_by"])

    return AttachReferralResponse(
        message="Referral successfully attached.",
        wallet_address=investor.wallet_address,
        referred_by=investor.referred_by,
    )


@router.get(
    "/stats/{wallet_address}",
    response_model=ReferralStatsResponse,
    summary="Get referral stats",
)
async def get_referral_stats(wallet_address: str) -> ReferralStatsResponse:
    if not validate_wallet_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format.",
        )

    investor = await Investor.get_or_none(wallet_address=wallet_address)

    if not investor:
        return ReferralStatsResponse(
            referral_code=None,
            total_referral_earnings_usd=0.0,
            total_referral_earnings_tokens=0.0,
            referral_count=0,
        )

    return ReferralStatsResponse(
        referral_code=investor.referral_code,
        total_referral_earnings_usd=float(investor.total_referral_earnings_usd),
        total_referral_earnings_tokens=scale_from_chain(
            investor.total_referral_earnings_tokens
        ),
        referral_count=investor.referral_count,
    )
