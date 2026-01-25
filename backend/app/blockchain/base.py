"""
Abstract base classes for blockchain integrations.

This module defines the interfaces that all blockchain implementations must follow.
To add support for a new blockchain (e.g., Ethereum, Tron):
1. Create a new module in app/blockchain/chains/
2. Implement the abstract classes defined here
3. Register the implementation in the blockchain registry
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


class BlockchainType(str, Enum):
    """Supported blockchain types."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"  # Future
    TRON = "tron"          # Future
    BSC = "bsc"            # Future
    POLYGON = "polygon"    # Future


@dataclass
class ChainConfig:
    """Configuration for a blockchain."""
    chain_type: BlockchainType
    rpc_url: str
    program_id: str  # Contract/Program address
    presale_token_address: str
    treasury_address: str
    payment_tokens: Dict[str, str]  # Symbol -> Address mapping
    chain_id: Optional[int] = None  # For EVM chains
    
    
@dataclass
class PurchaseAuthorization:
    """Blockchain-agnostic purchase authorization result."""
    chain: BlockchainType
    buyer_address: str
    payment_type: str
    payment_token_address: Optional[str]
    payment_amount: int
    token_amount: int
    nonce: int
    signature: str  # Encoded signature
    message: str    # Encoded message
    signer_public_key: str
    extra_data: Dict[str, Any] = None  # Chain-specific data
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}


@dataclass
class VestingInfo:
    """Blockchain-agnostic vesting information."""
    chain: BlockchainType
    wallet_address: str
    total_purchased: int
    claimed_amount: int
    vested_amount: int
    claimable_amount: int
    vesting_start_time: int
    cliff_end_time: int
    vesting_end_time: int
    vesting_percentage: float


@dataclass
class PresaleConfig:
    """Blockchain-agnostic presale configuration."""
    chain: BlockchainType
    program_id: str
    presale_token_address: str
    treasury_address: str
    payment_tokens: Dict[str, Optional[str]]  # Symbol -> Address (None for native)
    token_price_per_unit: int
    cliff_duration: int
    vesting_start_time: int
    vesting_duration: int
    is_active: bool
    total_sold: int


class BlockchainService(ABC):
    """
    Abstract base class for blockchain RPC interactions.
    
    Each blockchain implementation must provide methods for:
    - Connecting to the blockchain
    - Deriving addresses (PDAs, contract addresses)
    - Fetching account/contract data
    - Checking nonce status on-chain
    """
    
    @property
    @abstractmethod
    def chain_type(self) -> BlockchainType:
        """Return the blockchain type."""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the blockchain."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close blockchain connection."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the blockchain."""
        pass
    
    @abstractmethod
    def get_config_address(self) -> Tuple[str, Optional[int]]:
        """
        Get the presale config/contract address.
        Returns: (address, bump/nonce if applicable)
        """
        pass
    
    @abstractmethod
    def get_vesting_address(self, buyer: str) -> Tuple[str, Optional[int]]:
        """
        Get the vesting account/storage address for a buyer.
        Returns: (address, bump/nonce if applicable)
        """
        pass
    
    @abstractmethod
    def get_nonce_address(self, buyer: str, nonce: int) -> Tuple[str, Optional[int]]:
        """
        Get the nonce tracking address.
        Returns: (address, bump/nonce if applicable)
        """
        pass
    
    @abstractmethod
    async def get_account_data(self, address: str) -> Optional[bytes]:
        """Fetch raw account/contract data."""
        pass
    
    @abstractmethod
    async def is_nonce_used(self, buyer: str, nonce: int) -> bool:
        """Check if a nonce has been used on-chain."""
        pass
    
    @abstractmethod
    async def get_vesting_info(self, wallet_address: str) -> Optional[VestingInfo]:
        """Fetch and parse vesting information for a wallet."""
        pass
    
    @abstractmethod
    async def get_presale_config(self) -> Optional[PresaleConfig]:
        """Fetch and parse presale configuration."""
        pass
    
    @abstractmethod
    def get_pda_addresses(self, wallet_address: str) -> Dict[str, Dict[str, Any]]:
        """Get all relevant PDA/derived addresses for a wallet."""
        pass


class SignatureService(ABC):
    """
    Abstract base class for signature generation.
    
    Each blockchain has different signature schemes:
    - Solana: ed25519
    - Ethereum/BSC/Polygon: secp256k1 (EIP-712 typed data)
    - Tron: secp256k1
    """
    
    @property
    @abstractmethod
    def chain_type(self) -> BlockchainType:
        """Return the blockchain type."""
        pass
    
    @property
    @abstractmethod
    def signer_public_key(self) -> str:
        """Get the signer's public key/address."""
        pass
    
    @abstractmethod
    def get_payment_type_id(self, payment_type: str) -> int:
        """Convert payment type string to numeric ID."""
        pass
    
    @abstractmethod
    def get_payment_token_address(self, payment_type: str) -> Optional[str]:
        """Get the token address for a payment type (None for native)."""
        pass
    
    @abstractmethod
    def construct_message(
        self,
        buyer: str,
        payment_token: Optional[str],
        payment_type: int,
        payment_amount: int,
        token_amount: int,
        nonce: int,
    ) -> bytes:
        """Construct the message to be signed."""
        pass
    
    @abstractmethod
    def sign_message(self, message: bytes) -> bytes:
        """Sign a message with the authorized signer's private key."""
        pass
    
    @abstractmethod
    def generate_purchase_authorization(
        self,
        buyer_address: str,
        payment_type: str,
        payment_amount: int,
        token_amount: int,
        nonce: int,
    ) -> PurchaseAuthorization:
        """Generate a complete purchase authorization."""
        pass


class NonceService(ABC):
    """
    Abstract base class for nonce management.
    
    Nonces prevent replay attacks. Each implementation should:
    - Generate unique nonces
    - Track pending nonces (in cache/DB)
    - Verify against on-chain state
    """
    
    @property
    @abstractmethod
    def chain_type(self) -> BlockchainType:
        """Return the blockchain type."""
        pass
    
    @abstractmethod
    async def generate_nonce(self, wallet: str) -> int:
        """Generate a unique nonce for a wallet."""
        pass
    
    @abstractmethod
    async def is_nonce_available(self, wallet: str, nonce: int) -> bool:
        """Check if a nonce is available for use."""
        pass
    
    @abstractmethod
    async def mark_nonce_pending(self, wallet: str, nonce: int) -> None:
        """Mark a nonce as pending (signature generated)."""
        pass
    
    @abstractmethod
    async def mark_nonce_used(self, wallet: str, nonce: int) -> None:
        """Mark a nonce as used (transaction confirmed)."""
        pass
