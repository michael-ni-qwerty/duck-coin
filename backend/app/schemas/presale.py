from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Invoice / Payment creation ---

class CreateInvoiceRequest(BaseModel):
    """Request to create a NOWPayments invoice for token purchase."""
    wallet_address: str = Field(..., description="Buyer's wallet address on the source chain")
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


class PaymentResponse(BaseModel):
    """Details of a payment."""
    id: str
    wallet_address: str
    nowpayments_invoice_id: Optional[str]
    nowpayments_payment_id: Optional[int]
    nowpayments_order_id: Optional[str]
    price_amount_usd: float
    token_amount: int
    pay_amount: Optional[float]
    pay_currency: Optional[str]
    actually_paid: Optional[float]
    payment_status: str
    credit_status: str
    credit_tx_signature: Optional[str]
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime]
    credited_at: Optional[datetime]


class PaymentListResponse(BaseModel):
    """List of payments."""
    items: list[PaymentResponse]
    total_count: int


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


# --- Smart-contract interaction ---

class ClaimRequest(BaseModel):
    """Request to prepare an unsigned claim transaction payload for wallet signing."""
    wallet_address: str = Field(..., description="Investor/source wallet address")
    solana_wallet: Optional[str] = Field(
        None,
        description="Destination Solana wallet that signs the claim transaction.",
    )
    user_token_account: Optional[str] = Field(
        None,
        description="Optional user SPL token account. If omitted, backend derives the user's ATA for the sale mint.",
    )


class ClaimResponse(BaseModel):
    """Unsigned claim payload response for client-side signing."""
    wallet_address: str
    resolved_solana_wallet: str
    user_token_account: str
    recent_blockhash: str
    unsigned_tx_base64: str


class GetMessageResponse(BaseModel):
    message: str = Field(..., description="The message to be signed by the user")

class BindClaimWalletRequest(BaseModel):
    wallet_address: str = Field(..., description="EVM wallet address that made the purchase")
    solana_wallet: str = Field(..., description="Solana wallet address to bind as claim authority")
    signature: str = Field(..., description="The signature of the message")


class BindClaimWalletResponse(BaseModel):
    tx_signature: str = Field(..., description="The transaction signature of the on-chain binding")


class ContractStatusResponse(BaseModel):
    """High-level current contract state."""
    status: str
    is_active: bool
    is_token_launched: bool
    tge_percentage: int
    global_unlock_pct: int
    start_time: int


class LeaderboardEntryResponse(BaseModel):
    """Single leaderboard row."""
    rank: int
    wallet_address: str
    total_invested_usd: float
    total_tokens: int
    payment_count: int
    last_invested_at: Optional[datetime] = None


class LeaderboardResponse(BaseModel):
    """Leaderboard response."""
    total_count: int
    items: list[LeaderboardEntryResponse]
