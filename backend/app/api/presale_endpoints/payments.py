import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.core.constants import TOKEN_DECIMALS
from app.models.presale import CreditStatus, Payment, PaymentStatus, Investor
from app.schemas.presale import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    PaymentResponse,
    PaymentListResponse,
)
from app.services.nowpayments import NOWPaymentsClient, nowpayments_client
from app.services.solana import solana_service

from .common import (
    build_order_id,
    calculate_token_amount,
    validate_wallet_address,
    upsert_investor,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_referral_reward(payment: Payment) -> None:
    """Process referral reward logic and execute on-chain allocation for the referrer."""
    if not payment.referral_code:
        return

    try:
        referrer = await Investor.get_or_none(referral_code=payment.referral_code)
        if not referrer or referrer.wallet_address == payment.wallet_address:
            return

        # Calculate 10% reward
        reward_tokens = int(payment.token_amount * 0.1)
        reward_usd = float(payment.price_amount_usd) * 0.1
        reward_usd_raw = int(reward_usd * 10**6)

        # Update payment record with reward info
        payment.referral_reward_usd = reward_usd
        payment.referral_reward_tokens = reward_tokens

        # Call on-chain credit_allocation for the referrer
        referrer_tx_sig = await solana_service.credit_allocation(
            wallet_address=referrer.wallet_address,
            token_amount=reward_tokens,
            usd_amount=reward_usd_raw,
            payment_id=f"ref_{payment.id}",
        )
        logger.info(
            f"Credited referral allocation for {referrer.wallet_address}: tx={referrer_tx_sig}"
        )

        # Update referrer stats in DB
        referrer.total_referral_earnings_usd += reward_usd
        referrer.total_referral_earnings_tokens += reward_tokens

        # Use extra_data to track referred wallets
        if "referred_wallets" not in referrer.extra_data:
            referrer.extra_data["referred_wallets"] = []

        if payment.wallet_address not in referrer.extra_data["referred_wallets"]:
            referrer.extra_data["referred_wallets"].append(payment.wallet_address)
            referrer.referral_count += 1

        await referrer.save()

        # Update the referrer's main investor allocation stats as well
        allocation_data_referrer = await solana_service.get_allocation_data(
            referrer.wallet_address
        )
        referrer_launching_tokens = (
            allocation_data_referrer["claimable_amount"]
            if allocation_data_referrer
            else 0
        )
        # Re-calculate totals locally and update DB launching_tokens
        referrer.total_invested_usd += reward_usd
        referrer.total_tokens += reward_tokens
        if referrer_launching_tokens > 0:
            referrer.launching_tokens = referrer_launching_tokens
        await referrer.save()

    except Exception as ref_err:
        logger.error(
            f"Failed to process referral rewards for payment {payment.id}: {ref_err}"
        )


async def handle_successful_payment(payment: Payment) -> None:
    """Handle on-chain and DB state updates when a payment is marked as finished."""
    try:
        usd_amount_raw = int(float(payment.price_amount_usd) * 10**6)
        tx_sig = await solana_service.credit_allocation(
            wallet_address=payment.wallet_address,
            token_amount=payment.token_amount,
            usd_amount=usd_amount_raw,
            payment_id=str(payment.id),
        )
        payment.credit_status = CreditStatus.CREDITED
        payment.credit_tx_signature = tx_sig
        payment.credited_at = datetime.now(timezone.utc)
        logger.info(f"Credited allocation for payment {payment.id}: tx={tx_sig}")

        # Process referral rewards
        await process_referral_reward(payment)

        try:
            # Fetch updated on-chain allocation to get claimable_amount (launching_tokens)
            allocation_data = await solana_service.get_allocation_data(
                payment.wallet_address
            )
            launching_tokens = (
                allocation_data["claimable_amount"] if allocation_data else 0
            )
            await upsert_investor(payment, launching_tokens)
        except Exception as inv_err:
            logger.error(
                f"Failed to upsert investor for {payment.wallet_address}: {inv_err}"
            )

    except Exception as e:
        logger.error(f"Failed to credit allocation for payment {payment.id}: {e}")
        payment.credit_status = CreditStatus.FAILED
        payment.credit_error = str(e)


@router.get(
    "/status/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment status",
    description="Get the current status of a payment by its internal ID.",
)
async def get_payment_status(payment_id: str) -> PaymentResponse:
    """Get the current status of a payment."""
    payment = await Payment.get_or_none(id=payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Optional: Update status from NOWPayments if it's in a pending state
    if (
        payment.payment_status
        in [PaymentStatus.WAITING, PaymentStatus.CONFIRMING, PaymentStatus.SENDING]
        and payment.nowpayments_payment_id
    ):
        try:
            nowpayments_status = await nowpayments_client.get_payment_status(
                payment.nowpayments_payment_id
            )
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
            new_status_str = str(nowpayments_status.get("payment_status", ""))
            new_status = status_map.get(new_status_str)

            if new_status and new_status != payment.payment_status:
                payment.payment_status = new_status
                if new_status == PaymentStatus.FINISHED:
                    payment.paid_at = datetime.now(timezone.utc)
                await payment.save()
        except Exception as e:
            logger.error(f"Failed to update payment status from NOWPayments: {e}")

    return PaymentResponse(
        id=str(payment.id),
        wallet_address=payment.wallet_address,
        nowpayments_invoice_id=payment.nowpayments_invoice_id,
        nowpayments_payment_id=payment.nowpayments_payment_id,
        nowpayments_order_id=payment.nowpayments_order_id,
        price_amount_usd=float(payment.price_amount_usd),
        token_amount=payment.token_amount,
        pay_amount=float(payment.pay_amount) if payment.pay_amount else None,
        pay_currency=payment.pay_currency,
        actually_paid=float(payment.actually_paid) if payment.actually_paid else None,
        payment_status=payment.payment_status.value,
        credit_status=payment.credit_status.value,
        credit_tx_signature=payment.credit_tx_signature,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        paid_at=payment.paid_at,
        credited_at=payment.credited_at,
    )


@router.get(
    "/list",
    response_model=PaymentListResponse,
    summary="List payments",
    description="List all payments for a given wallet address.",
)
async def list_payments(
    wallet_address: str, limit: int = 50, offset: int = 0
) -> PaymentListResponse:
    """List payments for a specific wallet address."""
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="wallet_address is required",
        )

    payments_qs = Payment.filter(wallet_address=wallet_address)
    total_count = await payments_qs.count()
    payments = await payments_qs.order_by("-created_at").offset(offset).limit(limit)

    items = [
        PaymentResponse(
            id=str(p.id),
            wallet_address=p.wallet_address,
            nowpayments_invoice_id=p.nowpayments_invoice_id,
            nowpayments_payment_id=p.nowpayments_payment_id,
            nowpayments_order_id=p.nowpayments_order_id,
            price_amount_usd=float(p.price_amount_usd),
            token_amount=p.token_amount,
            pay_amount=float(p.pay_amount) if p.pay_amount else None,
            pay_currency=p.pay_currency,
            actually_paid=float(p.actually_paid) if p.actually_paid else None,
            payment_status=p.payment_status.value,
            credit_status=p.credit_status.value,
            credit_tx_signature=p.credit_tx_signature,
            created_at=p.created_at,
            updated_at=p.updated_at,
            paid_at=p.paid_at,
            credited_at=p.credited_at,
        )
        for p in payments
    ]

    return PaymentListResponse(
        items=items,
        total_count=total_count,
    )


@router.post(
    "/create-invoice",
    response_model=CreateInvoiceResponse,
    summary="Create a payment invoice",
    description="Creates a NOWPayments invoice. User is redirected to the hosted payment page to pay with any supported crypto.",
)
async def create_invoice(request: CreateInvoiceRequest) -> CreateInvoiceResponse:
    """Create a NOWPayments invoice for token purchase."""
    wallet_address = request.wallet_address.strip()
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="wallet_address is required",
        )

    if not validate_wallet_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported wallet_address format. Expected Solana or EVM address.",
        )

    # TODO: uncomment limits after testing
    # now = datetime.now(timezone.utc)
    # active_statuses = [
    #     PaymentStatus.WAITING,
    #     PaymentStatus.CONFIRMING,
    #     PaymentStatus.CONFIRMED,
    #     PaymentStatus.SENDING,
    #     PaymentStatus.PARTIALLY_PAID,
    # ]

    # rate_window_start = now - timedelta(seconds=settings.invoice_rate_limit_window_seconds)
    # recent_invoice_count = await Payment.filter(
    #     wallet_address=wallet_address,
    #     created_at__gte=rate_window_start,
    # ).count()
    # if recent_invoice_count >= settings.invoice_rate_limit_max_per_window:
    #     raise HTTPException(
    #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    #         detail="Too many invoice requests. Please try again later.",
    #     )

    # active_window_start = now - timedelta(hours=settings.invoice_active_window_hours)
    # active_invoice_count = await Payment.filter(
    #     wallet_address=wallet_address,
    #     payment_status__in=active_statuses,
    #     created_at__gte=active_window_start,
    # ).count()
    # if active_invoice_count >= settings.invoice_max_active_per_wallet:
    #     raise HTTPException(
    #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    #         detail="Too many active invoices for this wallet. Complete or wait for existing invoices first.",
    #     )

    token_amount = calculate_token_amount(request.usd_amount)
    order_id = build_order_id()
    if not settings.public_api_base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: public_api_base_url is required for NOWPayments IPN callbacks",
        )

    ipn_callback_url = f"{settings.public_api_base_url.rstrip('/')}{settings.api_v1_prefix}/presale/ipn-webhook"

    payment = await Payment.create(
        wallet_address=wallet_address,
        claim_wallet_solana=None,
        nowpayments_order_id=order_id,
        price_amount_usd=request.usd_amount,
        token_amount=token_amount,
        payment_status=PaymentStatus.WAITING,
        credit_status=CreditStatus.PENDING,
        referral_code=request.referral_code,
    )

    try:
        invoice = await nowpayments_client.create_invoice(
            price_amount=request.usd_amount,
            price_currency="usd",
            order_id=order_id,
            order_description=f"DuckCoin Presale - {token_amount / TOKEN_DECIMALS:.0f} DUCK tokens",
            ipn_callback_url=ipn_callback_url,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except Exception as e:
        logger.error(f"Failed to create NOWPayments invoice: {e}")
        payment.payment_status = PaymentStatus.FAILED
        await payment.save()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create payment invoice",
        )

    invoice_id = str(invoice.get("id", ""))
    payment.nowpayments_invoice_id = invoice_id
    await payment.save()

    return CreateInvoiceResponse(
        payment_id=str(payment.id),
        invoice_url=invoice.get("invoice_url", ""),
        invoice_id=invoice_id,
        token_amount=token_amount,
        usd_amount=request.usd_amount,
    )


@router.post(
    "/ipn-webhook",
    summary="NOWPayments IPN webhook",
    description="Receives payment status updates from NOWPayments. Verifies HMAC signature and credits allocation on-chain.",
    include_in_schema=False,
)
async def ipn_webhook(request: Request) -> dict[str, str]:
    """Handle NOWPayments IPN (Instant Payment Notification) callback."""
    body = await request.body()

    sig = request.headers.get("x-nowpayments-sig", "")
    if not NOWPaymentsClient.verify_ipn_signature(body, sig):
        logger.warning("IPN signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
        )

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

    payment = await Payment.filter(nowpayments_order_id=order_id).first()
    if not payment:
        logger.warning(f"IPN for unknown order_id: {order_id}")
        return {"status": "ignored"}

    if payment_id:
        payment.nowpayments_payment_id = int(payment_id)
    if pay_amount:
        payment.pay_amount = pay_amount
    if pay_currency:
        payment.pay_currency = pay_currency
    if actually_paid:
        payment.actually_paid = actually_paid

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

    if (
        new_status == PaymentStatus.FINISHED
        and payment.credit_status == CreditStatus.PENDING
    ):
        payment.paid_at = datetime.now(timezone.utc)
        await payment.save()
        await handle_successful_payment(payment)

    await payment.save()
    return {"status": "ok"}
