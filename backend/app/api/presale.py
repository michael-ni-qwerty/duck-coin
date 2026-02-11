import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.models.presale import Payment, PaymentStatus, CreditStatus, Investor
from app.schemas.presale import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    PaymentStatusResponse,
    PaymentListResponse,
    AllocationResponse,
    PresaleConfigResponse,
    PresaleStatsResponse,
    InvestorResponse,
    InvestorUpdateRequest,
)
from app.services.nowpayments import nowpayments_client, NOWPaymentsClient
from app.services.solana import solana_service
from app.core.config import settings
from app.core.constants import TOKEN_DECIMALS
from app.workers.tokenomics import SCHEDULE, TOTAL_DAYS, PRICE_PRECISION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presale", tags=["presale"])


def _get_current_price_usd() -> float:
    """Return the current token price in USD based on the tokenomics schedule."""
    if not settings.presale_start_date:
        return SCHEDULE[1].price_usd / PRICE_PRECISION
    start = date.fromisoformat(settings.presale_start_date)
    today = datetime.now(timezone.utc).date()
    day = (today - start).days + 1
    day = max(1, min(day, TOTAL_DAYS))
    return SCHEDULE[day].price_usd / PRICE_PRECISION


def _calculate_token_amount(usd_amount: float) -> int:
    """Calculate token amount (in smallest units) for a given USD amount."""
    price = _get_current_price_usd()
    tokens = usd_amount / price
    return int(tokens * TOKEN_DECIMALS)


async def _upsert_investor(payment: Payment) -> None:
    """Create or update the Investor record after a successful credit."""
    now = datetime.now(timezone.utc)
    investor, created = await Investor.get_or_create(
        wallet_address=payment.wallet_address,
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


# --- Create Invoice ---

@router.post(
    "/create-invoice",
    response_model=CreateInvoiceResponse,
    summary="Create a payment invoice",
    description="Creates a NOWPayments invoice. User is redirected to the hosted payment page to pay with any supported crypto.",
)
async def create_invoice(request: CreateInvoiceRequest) -> CreateInvoiceResponse:
    """Create a NOWPayments invoice for token purchase."""

    token_amount = _calculate_token_amount(request.usd_amount)
    order_id = str(uuid.uuid4())

    # Create DB record first
    payment = await Payment.create(
        wallet_address=request.wallet_address,
        nowpayments_order_id=order_id,
        price_amount_usd=request.usd_amount,
        token_amount=token_amount,
        payment_status=PaymentStatus.WAITING,
        credit_status=CreditStatus.PENDING,
    )

    # Create NOWPayments invoice
    try:
        invoice = await nowpayments_client.create_invoice(
            price_amount=request.usd_amount,
            price_currency="usd",
            order_id=order_id,
            order_description=f"DuckCoin Presale - {token_amount / TOKEN_DECIMALS:.0f} DUCK tokens",
            ipn_callback_url=f"{settings.api_v1_prefix}/presale/ipn-webhook",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except Exception as e:
        logger.error(f"Failed to create NOWPayments invoice: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create payment invoice",
        )

    # Update payment record with invoice ID
    invoice_id = str(invoice.get("id", ""))
    payment.nowpayments_invoice_id = invoice_id
    await payment.save()

    invoice_url = invoice.get("invoice_url", "")

    return CreateInvoiceResponse(
        payment_id=str(payment.id),
        invoice_url=invoice_url,
        invoice_id=invoice_id,
        token_amount=token_amount,
        usd_amount=request.usd_amount,
    )


# --- IPN Webhook ---

@router.post(
    "/ipn-webhook",
    summary="NOWPayments IPN webhook",
    description="Receives payment status updates from NOWPayments. Verifies HMAC signature and credits allocation on-chain.",
    include_in_schema=False,
)
async def ipn_webhook(request: Request):
    """Handle NOWPayments IPN (Instant Payment Notification) callback."""

    body = await request.body()

    # Verify HMAC signature
    sig = request.headers.get("x-nowpayments-sig", "")
    if not NOWPaymentsClient.verify_ipn_signature(body, sig):
        logger.warning("IPN signature verification failed")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    import json
    payload = json.loads(body)
    logger.info(f"IPN received: {payload}")

    payment_id = payload.get("payment_id")
    payment_status_str = payload.get("payment_status", "")
    order_id = payload.get("order_id")
    pay_amount = payload.get("pay_amount")
    pay_currency = payload.get("pay_currency")
    actually_paid = payload.get("actually_paid")

    if not order_id:
        logger.warning("IPN missing order_id")
        return {"status": "ignored"}

    # Find payment record
    payment = await Payment.filter(nowpayments_order_id=order_id).first()
    if not payment:
        logger.warning(f"IPN for unknown order_id: {order_id}")
        return {"status": "ignored"}

    # Update payment info
    if payment_id:
        payment.nowpayments_payment_id = int(payment_id)
    if pay_amount:
        payment.pay_amount = pay_amount
    if pay_currency:
        payment.pay_currency = pay_currency
    if actually_paid:
        payment.actually_paid = actually_paid

    # Map NOWPayments status
    status_map = {
        "waiting": PaymentStatus.WAITING,
        "confirming": PaymentStatus.CONFIRMING,
        "confirmed": PaymentStatus.CONFIRMED,
        "sending": PaymentStatus.SENDING,
        "partially_paid": PaymentStatus.PARTIALLY_PAID,
        "finished": PaymentStatus.FINISHED,
        "failed": PaymentStatus.FAILED,
        "refunded": PaymentStatus.REFUNDED,
        "expired": PaymentStatus.EXPIRED,
    }
    new_status = status_map.get(payment_status_str)
    if new_status:
        payment.payment_status = new_status

    # Credit on-chain when payment is finished
    if new_status == PaymentStatus.FINISHED and payment.credit_status == CreditStatus.PENDING:
        payment.paid_at = datetime.now(timezone.utc)
        await payment.save()

        try:
            usd_amount_raw = int(float(payment.price_amount_usd) * 10**6)  # 6 decimal precision
            tx_sig = await solana_service.credit_allocation(
                user_pubkey_str=payment.wallet_address,
                token_amount=payment.token_amount,
                usd_amount=usd_amount_raw,
                payment_id=str(payment.id),
            )
            payment.credit_status = CreditStatus.CREDITED
            payment.credit_tx_signature = tx_sig
            payment.credited_at = datetime.now(timezone.utc)
            logger.info(f"Credited allocation for payment {payment.id}: tx={tx_sig}")

            # Upsert investor record
            try:
                await _upsert_investor(payment)
            except Exception as inv_err:
                logger.error(f"Failed to upsert investor for {payment.wallet_address}: {inv_err}")
        except Exception as e:
            logger.error(f"Failed to credit allocation for payment {payment.id}: {e}")
            payment.credit_status = CreditStatus.FAILED
            payment.credit_error = str(e)

    await payment.save()
    return {"status": "ok"}


# --- Payment Status ---

@router.get(
    "/payment/{payment_id}",
    response_model=PaymentStatusResponse,
    summary="Get payment status",
)
async def get_payment_status(payment_id: str) -> PaymentStatusResponse:
    """Get the status of a specific payment."""
    payment = await Payment.get_or_none(id=payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return PaymentStatusResponse(
        payment_id=str(payment.id),
        wallet_address=payment.wallet_address,
        usd_amount=float(payment.price_amount_usd),
        token_amount=payment.token_amount,
        pay_currency=payment.pay_currency,
        payment_status=payment.payment_status.value,
        credit_status=payment.credit_status.value,
        credit_tx_signature=payment.credit_tx_signature,
        created_at=payment.created_at,
        paid_at=payment.paid_at,
        credited_at=payment.credited_at,
    )


# --- Payments by wallet ---

@router.get(
    "/payments/{wallet_address}",
    response_model=PaymentListResponse,
    summary="Get payments for a wallet",
)
async def get_wallet_payments(wallet_address: str) -> PaymentListResponse:
    """Get all payments for a specific wallet address."""
    payments = await Payment.filter(wallet_address=wallet_address).order_by("-created_at")

    items = [
        PaymentStatusResponse(
            payment_id=str(p.id),
            wallet_address=p.wallet_address,
            usd_amount=float(p.price_amount_usd),
            token_amount=p.token_amount,
            pay_currency=p.pay_currency,
            payment_status=p.payment_status.value,
            credit_status=p.credit_status.value,
            credit_tx_signature=p.credit_tx_signature,
            created_at=p.created_at,
            paid_at=p.paid_at,
            credited_at=p.credited_at,
        )
        for p in payments
    ]

    return PaymentListResponse(
        wallet_address=wallet_address,
        payments=items,
        total_count=len(items),
    )


# --- On-chain allocation ---

@router.get(
    "/allocation/{wallet_address}",
    response_model=AllocationResponse,
    summary="Get on-chain allocation for a wallet",
)
async def get_allocation(wallet_address: str) -> AllocationResponse:
    """Get the on-chain token allocation for a wallet."""
    data = await solana_service.get_allocation_data(wallet_address)

    if data is None:
        return AllocationResponse(wallet_address=wallet_address)

    return AllocationResponse(
        wallet_address=wallet_address,
        amount_purchased=data["amount_purchased"],
        amount_claimed=data["amount_claimed"],
        claimable_amount=data["claimable_amount"],
    )


# --- Presale config ---

@router.get(
    "/config",
    response_model=PresaleConfigResponse,
    summary="Get on-chain presale configuration",
)
async def get_presale_config() -> PresaleConfigResponse:
    """Get the current presale configuration from on-chain."""
    config = await solana_service.get_config_data()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presale config not found on-chain",
        )

    return PresaleConfigResponse(
        program_id=settings.presale_program_id,
        token_mint=config["token_mint"],
        token_price_usd=config["token_price_usd"],
        tge_percentage=config["tge_percentage"],
        start_time=config["start_time"],
        daily_cap=config["daily_cap"],
        total_sold=config["total_sold"],
        presale_supply=config["presale_supply"],
        total_burned=config["total_burned"],
        status=config["status"],
        total_raised_usd=config["total_raised_usd"],
        sold_today=config["sold_today"],
    )


# --- Presale stats ---

@router.get(
    "/stats",
    response_model=PresaleStatsResponse,
    summary="Get presale statistics",
)
async def get_presale_stats() -> PresaleStatsResponse:
    """Get aggregate presale statistics from on-chain + DB."""
    config = await solana_service.get_config_data()

    total_participants = await Payment.filter(
        credit_status=CreditStatus.CREDITED
    ).distinct().values_list("wallet_address", flat=True)

    if config:
        return PresaleStatsResponse(
            total_sold=config["total_sold"],
            total_raised_usd=config["total_raised_usd"],
            total_participants=len(set(total_participants)),
            presale_supply=config["presale_supply"],
            is_active=config["status"] == "PresaleActive",
        )

    return PresaleStatsResponse(
        total_sold=0,
        total_raised_usd=0,
        total_participants=0,
        presale_supply=0,
        is_active=False,
    )


# --- Available currencies ---

@router.get(
    "/currencies",
    summary="Get available payment currencies",
)
async def get_currencies():
    """Get list of cryptocurrencies available for payment via NOWPayments."""
    try:
        currencies = await nowpayments_client.get_available_currencies()
        return {"currencies": currencies}
    except Exception as e:
        logger.error(f"Failed to fetch currencies: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch available currencies",
        )


# --- Price estimate ---

@router.get(
    "/estimate",
    summary="Get estimated crypto price for USD amount",
)
async def get_estimate(usd_amount: float, pay_currency: str = "btc"):
    """Get estimated amount in a specific crypto for a given USD amount."""
    try:
        estimate = await nowpayments_client.get_estimated_price(
            amount=usd_amount,
            currency_from="usd",
            currency_to=pay_currency,
        )
        token_amount = _calculate_token_amount(usd_amount)
        return {
            "usd_amount": usd_amount,
            "pay_currency": pay_currency,
            "estimated_amount": estimate.get("estimated_amount"),
            "token_amount": token_amount,
        }
    except Exception as e:
        logger.error(f"Failed to get estimate: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to get price estimate",
        )


# --- Investor endpoints ---

def _investor_to_response(inv: Investor) -> InvestorResponse:
    return InvestorResponse(
        wallet_address=inv.wallet_address,
        total_invested_usd=float(inv.total_invested_usd),
        total_tokens=inv.total_tokens,
        payment_count=inv.payment_count,
        extra_data=inv.extra_data or {},
        first_invested_at=inv.first_invested_at,
        last_invested_at=inv.last_invested_at,
        created_at=inv.created_at,
    )


@router.get(
    "/investor/{wallet_address}",
    response_model=InvestorResponse,
    summary="Get investor profile",
)
async def get_investor(wallet_address: str) -> InvestorResponse:
    """Get investor profile and aggregate data for a wallet."""
    investor = await Investor.get_or_none(wallet_address=wallet_address)
    if not investor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investor not found",
        )
    return _investor_to_response(investor)


@router.patch(
    "/investor/{wallet_address}",
    response_model=InvestorResponse,
    summary="Update investor profile",
)
async def update_investor(
    wallet_address: str, body: InvestorUpdateRequest
) -> InvestorResponse:
    """Update optional profile fields for an investor."""
    investor = await Investor.get_or_none(wallet_address=wallet_address)
    if not investor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investor not found",
        )

    investor.extra_data = body.extra_data
    await investor.save()

    return _investor_to_response(investor)


@router.get(
    "/investors",
    response_model=list[InvestorResponse],
    summary="List all investors",
)
async def list_investors(
    limit: int = 50,
    offset: int = 0,
    order_by: str = "-total_invested_usd",
) -> list[InvestorResponse]:
    """List investors ordered by total invested (descending by default)."""
    allowed_orders = {
        "total_invested_usd", "-total_invested_usd",
        "total_tokens", "-total_tokens",
        "payment_count", "-payment_count",
        "created_at", "-created_at",
        "last_invested_at", "-last_invested_at",
    }
    if order_by not in allowed_orders:
        order_by = "-total_invested_usd"

    investors = await Investor.all().order_by(order_by).offset(offset).limit(limit)
    return [_investor_to_response(inv) for inv in investors]
