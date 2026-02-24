import uuid
import re
from datetime import date, datetime, timezone

from app.core.config import settings
from app.core.constants import TOKEN_DECIMALS
from app.models.presale import Investor, Payment
from app.workers.tokenomics import PRICE_PRECISION, SCHEDULE, TOTAL_DAYS


WALLET_ADDRESS_REGEX_MAP: dict[str, re.Pattern[str]] = {
    "solana": re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"),
    "evm": re.compile(r"^0x[a-fA-F0-9]{40}$"),
}


def classify_wallet_address(wallet_address: str) -> str | None:
    """Classify wallet address format into normalized blockchain bucket."""
    address = wallet_address.strip()
    if not address:
        return None

    for blockchain, pattern in WALLET_ADDRESS_REGEX_MAP.items():
        if pattern.fullmatch(address):
            return blockchain

    return None


def validate_wallet_address(wallet_address: str) -> bool:
    """Validate wallet address against supported blockchain regex mapping."""
    return classify_wallet_address(wallet_address) is not None


def is_solana_wallet_address(wallet_address: str) -> bool:
    """Return True when wallet address format is Solana."""
    return classify_wallet_address(wallet_address) == "solana"


def get_current_price_usd() -> float:
    """Return the current token price in USD based on the tokenomics schedule."""
    if not settings.presale_start_date:
        return SCHEDULE[1].price_usd / PRICE_PRECISION

    start = date.fromisoformat(settings.presale_start_date)
    today = datetime.now(timezone.utc).date()
    day = (today - start).days + 1
    day = max(1, min(day, TOTAL_DAYS))
    return SCHEDULE[day].price_usd / PRICE_PRECISION


def calculate_token_amount(usd_amount: float) -> int:
    """Calculate token amount in smallest units for a given USD amount."""
    price = get_current_price_usd()
    tokens = usd_amount / price
    return int(tokens * TOKEN_DECIMALS)


def build_order_id() -> str:
    return str(uuid.uuid4())


async def upsert_investor(payment: Payment) -> None:
    """Create or update the Investor record after a successful credit."""
    now = datetime.now(timezone.utc)
    investor_wallet = payment.wallet_address
    investor, created = await Investor.get_or_create(
        wallet_address=investor_wallet,
        defaults={
            "total_invested_usd": payment.price_amount_usd,
            "total_tokens": payment.token_amount,
            "payment_count": 1,
            "first_invested_at": now,
            "last_invested_at": now,
        },
    )
    if not created:
        investor.total_invested_usd += payment.price_amount_usd
        investor.total_tokens += payment.token_amount
        investor.payment_count += 1
        investor.last_invested_at = now
        await investor.save()
