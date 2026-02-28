import uuid
import re
import secrets
import string
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


async def generate_unique_referral_code(length=8) -> str:
    """Generate a unique alphanumeric referral code."""
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = await Investor.filter(referral_code=code).exists()
        if not exists:
            return code
    # Fallback to longer code if space is congested (extremely unlikely)
    return "".join(secrets.choice(alphabet) for _ in range(length + 4))


async def upsert_investor(payment: Payment, launching_tokens: int = 0) -> None:
    """Create or update the Investor record after a successful credit."""
    now = datetime.now(timezone.utc)
    investor_wallet = payment.wallet_address

    # Auto-generate referral code for the investor if they don't have one yet
    investor = await Investor.get_or_none(wallet_address=investor_wallet)

    if not investor:
        # Creating new investor
        referral_code = await generate_unique_referral_code()

        investor = await Investor.create(
            wallet_address=investor_wallet,
            total_invested_usd=payment.price_amount_usd,
            total_tokens=payment.token_amount,
            launching_tokens=launching_tokens,
            payment_count=1,
            first_invested_at=now,
            last_invested_at=now,
            referral_code=referral_code,
        )
    else:
        # Updating existing investor
        investor.total_invested_usd += payment.price_amount_usd
        investor.total_tokens += payment.token_amount
        if launching_tokens > 0:
            investor.launching_tokens = launching_tokens
        investor.payment_count += 1
        investor.last_invested_at = now

        # Ensure older investors get a referral code
        if not investor.referral_code:
            investor.referral_code = await generate_unique_referral_code()

        await investor.save()
