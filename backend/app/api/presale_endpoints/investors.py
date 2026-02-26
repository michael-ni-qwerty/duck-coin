from fastapi import APIRouter, HTTPException, status

from app.models.presale import Investor
from app.schemas.presale import (
    InvestorInfoResponse,
    LeaderboardEntryResponse,
    LeaderboardResponse,
    PriceInfoResponse,
)
from app.workers.tokenomics import LISTING_PRICE_USD, get_today_token_data

router = APIRouter()


@router.get(
    "/info/{wallet_address}",
    response_model=InvestorInfoResponse,
    summary="Get investor info",
)
async def get_investor_info(wallet_address: str) -> InvestorInfoResponse:
    """Get detailed information about a specific investor."""
    investor = await Investor.get_or_none(wallet_address=wallet_address)

    if not investor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investor not found",
        )

    invested_usd = float(investor.total_invested_usd)
    launching_tokens = investor.launching_tokens if investor.launching_tokens else 0
    # launching_tokens is in smallest units, assuming 10^9 decimals
    tokens_whole = launching_tokens / (10**9)
    launch_evaluation = tokens_whole * LISTING_PRICE_USD

    return InvestorInfoResponse(
        wallet_address=investor.wallet_address,
        invested=invested_usd,
        tokens=investor.total_tokens,
        balance=invested_usd,
        launch_evaluation=launch_evaluation,
    )


@router.get(
    "/price",
    response_model=PriceInfoResponse,
    summary="Get token price info",
)
async def get_price_info() -> PriceInfoResponse:
    """Get current presale price and future launch price."""
    current_price_usd = get_today_token_data().price_usd

    return PriceInfoResponse(
        current_price_usd=current_price_usd,
        launch_price_usd=LISTING_PRICE_USD,
    )


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get leaderboard",
)
async def get_leaderboard(limit: int = 20, offset: int = 0) -> LeaderboardResponse:
    """Get leaderboard ranked by total invested USD."""
    investors = (
        await Investor.all().order_by("-total_invested_usd").offset(offset).limit(limit)
    )

    items = [
        LeaderboardEntryResponse(
            rank=offset + idx + 1,
            wallet_address=inv.wallet_address,
            total_invested_usd=float(inv.total_invested_usd),
            total_tokens=inv.total_tokens,
            payment_count=inv.payment_count,
            last_invested_at=inv.last_invested_at,
        )
        for idx, inv in enumerate(investors)
    ]

    return LeaderboardResponse(total_count=len(items), items=items)
