import logging
from fastapi import APIRouter, HTTPException, status

from app.models.presale import Investor
from app.schemas.presale import ReferralStatsResponse
from .common import validate_wallet_address

logger = logging.getLogger(__name__)
router = APIRouter()


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
        total_referral_earnings_tokens=float(investor.total_referral_earnings_tokens)
        / 10**9,
        referral_count=investor.referral_count,
    )
