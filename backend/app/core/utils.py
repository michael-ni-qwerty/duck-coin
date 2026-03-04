from decimal import Decimal

from app.core.config import settings

# Multiply on-chain integer amounts by 10^-decimals to get human-readable floats.
TOKEN_PRECISION = Decimal(10) ** settings.decimals


def scale_from_chain(value) -> float:
    """Convert on-chain integer values to human-readable decimals without float artifacts."""
    return float(Decimal(value) / TOKEN_PRECISION)


def scale_to_chain(value) -> int:
    """Convert human-readable decimals to on-chain integer values."""
    return int(Decimal(value) * TOKEN_PRECISION)
