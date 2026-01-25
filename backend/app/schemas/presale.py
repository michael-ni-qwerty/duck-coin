from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class BlockchainType(str, Enum):
    """Supported blockchain types."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    TRON = "tron"
    BSC = "bsc"
    POLYGON = "polygon"


class PaymentType(str, Enum):
    """Common payment types across chains."""
    NATIVE = "NATIVE"  # SOL, ETH, TRX, BNB, MATIC
    USDT = "USDT"
    USDC = "USDC"
    # Solana-specific aliases
    SOL = "SOL"


class PurchaseRequest(BaseModel):
    """Request to generate a purchase authorization signature."""
    chain: BlockchainType = Field(
        default=BlockchainType.SOLANA,
        description="Target blockchain"
    )
    buyer_wallet: str = Field(..., description="Buyer's wallet address")
    payment_type: PaymentType = Field(..., description="Payment currency type")
    payment_amount: int = Field(..., gt=0, description="Payment amount in smallest units")
    token_amount: int = Field(..., gt=0, description="Token amount to purchase in smallest units")


class PurchaseAuthorizationResponse(BaseModel):
    """Response containing the signed authorization for a purchase."""
    chain: BlockchainType
    buyer_wallet: str
    payment_type: str
    payment_token_address: Optional[str] = Field(None, description="Token contract address (None for native)")
    payment_amount: int
    token_amount: int
    nonce: int
    signature: str = Field(..., description="Encoded signature (format depends on chain)")
    message: str = Field(..., description="Encoded message that was signed")
    signer_public_key: str = Field(..., description="Public key/address of the authorized signer")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Chain-specific extra data")


class VestingInfoRequest(BaseModel):
    """Request to get vesting information for a wallet."""
    chain: BlockchainType = Field(default=BlockchainType.SOLANA, description="Target blockchain")
    wallet_address: str = Field(..., description="Wallet address to query")


class VestingInfoResponse(BaseModel):
    """Vesting information for a user."""
    chain: BlockchainType
    wallet_address: str
    total_purchased: int
    claimed_amount: int
    vested_amount: int
    claimable_amount: int
    vesting_start_time: int
    cliff_end_time: int
    vesting_end_time: int
    vesting_percentage: float = Field(..., ge=0, le=100)


class PresaleConfigResponse(BaseModel):
    """Current presale configuration."""
    chain: BlockchainType
    contract_address: str = Field(..., description="Program ID or contract address")
    presale_token_address: str
    treasury_address: str
    payment_tokens: Dict[str, Optional[str]] = Field(
        ..., 
        description="Payment token symbols to addresses (None for native)"
    )
    token_price_per_unit: int
    cliff_duration: int
    vesting_start_time: int
    vesting_duration: int
    is_active: bool
    total_sold: int


class PresaleStatsResponse(BaseModel):
    """Presale statistics."""
    chain: BlockchainType
    total_sold: int
    total_participants: int
    total_raised: Dict[str, int] = Field(
        ...,
        description="Total raised per payment type"
    )
    is_active: bool


class DerivedAddressesResponse(BaseModel):
    """Derived addresses for transaction building (PDAs, contract storage, etc.)."""
    chain: BlockchainType
    addresses: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Named addresses with their derivation data"
    )


class SupportedChainsResponse(BaseModel):
    """List of supported blockchains."""
    chains: list[BlockchainType]
    default_chain: BlockchainType


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    chain: Optional[BlockchainType] = None
