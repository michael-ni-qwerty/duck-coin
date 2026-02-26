from tortoise import fields, models
from enum import Enum


class PaymentStatus(str, Enum):
    WAITING = "waiting"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    SENDING = "sending"
    PARTIALLY_PAID = "partially_paid"
    FINISHED = "finished"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class CreditStatus(str, Enum):
    PENDING = "pending"
    CREDITED = "credited"
    FAILED = "failed"


class AuthMessage(models.Model):
    """Stores nonce messages for signature verification."""

    wallet_address = fields.CharField(max_length=128, pk=True)
    message = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        table = "auth_messages"


class Payment(models.Model):
    """Tracks a NOWPayments payment and its on-chain credit status."""

    id = fields.UUIDField(pk=True)

    # User info
    wallet_address = fields.CharField(max_length=128, index=True)
    claim_wallet_solana = fields.CharField(max_length=128, null=True, index=True)

    # NOWPayments data
    nowpayments_invoice_id = fields.CharField(max_length=64, null=True, index=True)
    nowpayments_payment_id = fields.BigIntField(null=True, unique=True)
    nowpayments_order_id = fields.CharField(max_length=128, null=True, index=True)

    # Amounts
    price_amount_usd = fields.DecimalField(max_digits=18, decimal_places=2)
    token_amount = fields.BigIntField()
    pay_amount = fields.DecimalField(max_digits=28, decimal_places=12, null=True)
    pay_currency = fields.CharField(max_length=20, null=True)
    actually_paid = fields.DecimalField(max_digits=28, decimal_places=12, null=True)

    # Status
    payment_status = fields.CharEnumField(
        PaymentStatus, max_length=20, default=PaymentStatus.WAITING
    )
    credit_status = fields.CharEnumField(
        CreditStatus, max_length=20, default=CreditStatus.PENDING
    )

    # On-chain
    credit_tx_signature = fields.CharField(max_length=128, null=True)
    credit_error = fields.TextField(null=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    paid_at = fields.DatetimeField(null=True)
    credited_at = fields.DatetimeField(null=True)

    class Meta:
        table = "payments"


class Investor(models.Model):
    """Aggregated investor profile per wallet address."""

    id = fields.UUIDField(pk=True)
    wallet_address = fields.CharField(max_length=128, unique=True, index=True)

    # Aggregated totals (updated on each credited payment)
    total_invested_usd = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_tokens = fields.BigIntField(default=0)
    launching_tokens = fields.BigIntField(default=0)
    payment_count = fields.IntField(default=0)

    # Flexible metadata (JSONB)
    extra_data = fields.JSONField(default=dict)

    # First / last activity
    first_invested_at = fields.DatetimeField(null=True)
    last_invested_at = fields.DatetimeField(null=True)

    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "investors"
