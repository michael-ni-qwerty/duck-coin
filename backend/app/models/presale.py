"""
Tortoise ORM models for the presale system.

These models track:
- Purchase transactions across all chains
- Vesting information (cached from on-chain)
- Nonce usage for replay protection
- Presale statistics
"""

from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from enum import Enum


class BlockchainType(str, Enum):
    """Supported blockchain types."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    TRON = "tron"
    BSC = "bsc"
    POLYGON = "polygon"


class PaymentType(str, Enum):
    """Payment token types."""
    NATIVE = "native"
    USDT = "usdt"
    USDC = "usdc"


class TransactionStatus(str, Enum):
    """Transaction status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class Purchase(models.Model):
    """
    Records of token purchases across all chains.
    
    This is the source of truth for purchase history and analytics.
    On-chain data is the source of truth for actual token balances.
    """
    id = fields.UUIDField(pk=True)
    
    # Blockchain info
    chain = fields.CharEnumField(BlockchainType, max_length=20, index=True)
    
    # Wallet info
    buyer_wallet = fields.CharField(max_length=128, index=True)
    
    # Payment details
    payment_type = fields.CharEnumField(PaymentType, max_length=20)
    payment_token_address = fields.CharField(max_length=128, null=True)
    payment_amount = fields.BigIntField()  # In smallest units
    
    # Token details
    token_amount = fields.BigIntField()  # In smallest units
    
    # Authorization
    nonce = fields.BigIntField()
    signature = fields.TextField()
    
    # Transaction
    tx_hash = fields.CharField(max_length=128, null=True, index=True)
    status = fields.CharEnumField(TransactionStatus, max_length=20, default=TransactionStatus.PENDING)
    
    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    confirmed_at = fields.DatetimeField(null=True)
    
    class Meta:
        table = "purchases"
        indexes = [
            ("chain", "buyer_wallet"),
            ("chain", "status"),
        ]


class VestingCache(models.Model):
    """
    Cached vesting information from on-chain.
    
    This is periodically synced from the blockchain to reduce RPC calls.
    The on-chain data is always the source of truth.
    """
    id = fields.UUIDField(pk=True)
    
    # Blockchain info
    chain = fields.CharEnumField(BlockchainType, max_length=20, index=True)
    
    # Wallet
    wallet_address = fields.CharField(max_length=128, index=True)
    
    # Vesting data (from on-chain)
    total_purchased = fields.BigIntField(default=0)
    claimed_amount = fields.BigIntField(default=0)
    
    # Cache metadata
    last_synced_at = fields.DatetimeField(auto_now=True)
    on_chain_address = fields.CharField(max_length=128, null=True)  # PDA or contract storage
    
    class Meta:
        table = "vesting_cache"
        unique_together = [("chain", "wallet_address")]


class NonceRecord(models.Model):
    """
    Persistent nonce tracking for replay protection.
    
    Redis is used for fast lookups, this is for persistence and auditing.
    """
    id = fields.UUIDField(pk=True)
    
    # Blockchain info
    chain = fields.CharEnumField(BlockchainType, max_length=20, index=True)
    
    # Wallet
    wallet_address = fields.CharField(max_length=128, index=True)
    
    # Nonce
    nonce = fields.BigIntField()
    
    # Status
    status = fields.CharField(max_length=20, default="pending")  # pending, used, expired
    
    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    used_at = fields.DatetimeField(null=True)
    
    class Meta:
        table = "nonce_records"
        unique_together = [("chain", "wallet_address", "nonce")]


class PresaleStats(models.Model):
    """
    Aggregated presale statistics per chain.
    
    Updated periodically or on significant events.
    """
    id = fields.UUIDField(pk=True)
    
    # Blockchain info
    chain = fields.CharEnumField(BlockchainType, max_length=20, unique=True)
    
    # Stats
    total_sold = fields.BigIntField(default=0)
    total_participants = fields.IntField(default=0)
    total_raised_native = fields.BigIntField(default=0)
    total_raised_usdt = fields.BigIntField(default=0)
    total_raised_usdc = fields.BigIntField(default=0)
    
    # Timestamps
    last_updated_at = fields.DatetimeField(auto_now=True)
    
    class Meta:
        table = "presale_stats"


# Pydantic models for API responses (auto-generated from Tortoise models)
Purchase_Pydantic = pydantic_model_creator(Purchase, name="Purchase")
PurchaseIn_Pydantic = pydantic_model_creator(Purchase, name="PurchaseIn", exclude_readonly=True)
VestingCache_Pydantic = pydantic_model_creator(VestingCache, name="VestingCache")
PresaleStats_Pydantic = pydantic_model_creator(PresaleStats, name="PresaleStats")
