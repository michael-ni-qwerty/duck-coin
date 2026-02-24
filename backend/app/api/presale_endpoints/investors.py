from fastapi import APIRouter

from app.models.presale import Investor
from app.schemas.presale import (
    LeaderboardEntryResponse,
    LeaderboardResponse,
)

router = APIRouter()


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get leaderboard",
)
async def get_leaderboard(limit: int = 20, offset: int = 0) -> LeaderboardResponse:
    """Get leaderboard ranked by total invested USD."""
    investors = await Investor.all().order_by("-total_invested_usd").offset(offset).limit(limit)

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
