from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Invoice / Payment creation ---

class CreateInvoiceRequest(BaseModel):
    """Request to create a NOWPayments invoice for token purchase."""
    wallet_address: str = Field(..., description="Buyer's Solana wallet address (pubkey)")
    usd_amount: float = Field(..., ge=50, description="Amount in USD to spend (minimum $50)")
    success_url: Optional[str] = Field(None, description="Redirect URL after successful payment")
    cancel_url: Optional[str] = Field(None, description="Redirect URL if payment cancelled")


class CreateInvoiceResponse(BaseModel):
    """Response with NOWPayments invoice details."""
    payment_id: str = Field(..., description="Internal payment record ID")
    invoice_url: str = Field(..., description="NOWPayments hosted payment page URL")
    invoice_id: str = Field(..., description="NOWPayments invoice ID")
    token_amount: int = Field(..., description="Token amount to be credited (in smallest units)")
    usd_amount: float


# --- Payment status ---

class PaymentStatusResponse(BaseModel):
    """Status of a payment."""
    payment_id: str
    wallet_address: str
    usd_amount: float
    token_amount: int
    pay_currency: Optional[str] = None
    payment_status: str
    credit_status: str
    credit_tx_signature: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    credited_at: Optional[datetime] = None


# --- Allocation / Vesting ---

class AllocationResponse(BaseModel):
    """On-chain allocation data for a wallet."""
    wallet_address: str
    amount_purchased: int = 0
    amount_claimed: int = 0
    claimable_amount: int = 0


# --- Presale config & stats ---

class PresaleConfigResponse(BaseModel):
    """Current on-chain presale configuration."""
    program_id: str
    token_mint: str
    token_price_usd: int
    tge_percentage: int
    start_time: int
    daily_cap: int
    total_sold: int
    presale_supply: int
    total_burned: int
    status: str
    total_raised_usd: int
    sold_today: int


class PresaleStatsResponse(BaseModel):
    """Aggregate presale statistics."""
    total_sold: int
    total_raised_usd: int
    total_participants: int
    presale_supply: int
    is_active: bool


# --- Payments history ---

class PaymentListResponse(BaseModel):
    """List of payments for a wallet."""
    wallet_address: str
    payments: list[PaymentStatusResponse]
    total_count: int


# --- Investor ---

class InvestorResponse(BaseModel):
    """Investor aggregate data."""
    wallet_address: str
    total_invested_usd: float
    total_tokens: int
    payment_count: int
    extra_data: dict = {}
    first_invested_at: Optional[datetime] = None
    last_invested_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class InvestorUpdateRequest(BaseModel):
    """Update the extra_data JSONB field for an investor."""
    extra_data: dict


# --- Error ---

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
