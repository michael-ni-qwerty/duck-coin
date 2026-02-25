import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.nowpayments import nowpayments_client

from .common import calculate_token_amount

logger = logging.getLogger(__name__)
router = APIRouter()

allowed_networks = {
    'ethereum', 'eth', 'bsc', 'binance-smart-chain', 'polygon', 'matic', 
    'arbitrum', 'arb', 'avalanche', 'avax', 'fantom', 'ftm', 'optimism',
    'op', 'base', 'linea', 'zkSync', 'zksync', 'cronos', 'cro', 'solana', 'sol'
}

temp_not_works = ("1inchbsc", "")

class CurrencyItemResponse(BaseModel):
    id: int
    code: str
    name: str
    enable: bool
    wallet_regex: str | None = None
    priority: int
    extra_id_exists: bool
    extra_id_regex: str | None = None
    logo_url: str | None = None
    track: bool
    cg_id: str | None = None
    is_maxlimit: bool
    network: str | None = None
    smart_contract: str | None = None
    network_precision: int | None = None


class CurrenciesResponse(BaseModel):
    currencies: list[CurrencyItemResponse]


class EstimateResponse(BaseModel):
    usd_amount: float
    pay_currency: str
    estimated_amount: float | None = None
    token_amount: int


@router.get(
    "/currencies",
    response_model=CurrenciesResponse,
    summary="Get available payment currencies",
)
async def get_currencies() -> CurrenciesResponse:
    """Get list of cryptocurrencies available for payment via NOWPayments."""
    try:
        currencies = await nowpayments_client.get_available_currencies()
        
        # Filter for EVM and Solana blockchains only
        allowed_currencies = []
        
        for currency in currencies:
            if currency and currency.get('network'):
                network = currency.get('network', '').lower()
                if network in allowed_networks and currency.get('code').lower() not in temp_not_works:
                    allowed_currencies.append(currency)
        
        return CurrenciesResponse(currencies=allowed_currencies)
    except Exception as e:
        logger.error(f"Failed to fetch currencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch available currencies",
        )


@router.get(
    "/estimate",
    response_model=EstimateResponse,
    summary="Get estimated crypto price for USD amount",
)
async def get_estimate(usd_amount: float, pay_currency: str = "btc") -> EstimateResponse:
    """Get estimated amount in a specific crypto for a given USD amount."""
    try:
        estimate = await nowpayments_client.get_estimated_price(
            amount=usd_amount,
            currency_from="usd",
            currency_to=pay_currency,
        )
        token_amount = calculate_token_amount(usd_amount)
        estimated_amount_raw = estimate.get("estimated_amount")
        estimated_amount = float(estimated_amount_raw) if estimated_amount_raw is not None else None

        return EstimateResponse(
            usd_amount=usd_amount,
            pay_currency=pay_currency,
            estimated_amount=estimated_amount,
            token_amount=token_amount,
        )
    except Exception as e:
        logger.error(f"Failed to get estimate: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to get price estimate",
        )
