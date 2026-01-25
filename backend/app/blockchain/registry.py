"""
Blockchain service registry.

This module provides a central registry for blockchain implementations.
New chains are registered here and can be accessed by type.
"""

from typing import Dict
from app.blockchain.base import (
    BlockchainType,
    BlockchainService,
    SignatureService,
    NonceService,
)


class BlockchainRegistry:
    """
    Registry for blockchain service implementations.
    
    Usage:
        # Register a chain
        registry.register(
            BlockchainType.SOLANA,
            blockchain_service=SolanaBlockchainService,
            signature_service=SolanaSignatureService,
            nonce_service=SolanaNonceService,
        )
        
        # Get services
        blockchain = registry.get_blockchain_service(BlockchainType.SOLANA)
        signer = registry.get_signature_service(BlockchainType.SOLANA)
    """
    
    def __init__(self):
        self._blockchain_services: Dict[BlockchainType, BlockchainService] = {}
        self._signature_services: Dict[BlockchainType, SignatureService] = {}
        self._nonce_services: Dict[BlockchainType, NonceService] = {}
        self._initialized: Dict[BlockchainType, bool] = {}
    
    def register(
        self,
        chain_type: BlockchainType,
        blockchain_service: BlockchainService,
        signature_service: SignatureService,
        nonce_service: NonceService,
    ) -> None:
        """
        Register blockchain service implementations.
        
        Args:
            chain_type: The blockchain type
            blockchain_service: Instance of BlockchainService
            signature_service: Instance of SignatureService
            nonce_service: Instance of NonceService
        """
        self._blockchain_services[chain_type] = blockchain_service
        self._signature_services[chain_type] = signature_service
        self._nonce_services[chain_type] = nonce_service
        self._initialized[chain_type] = True
    
    def is_registered(self, chain_type: BlockchainType) -> bool:
        """Check if a chain is registered."""
        return chain_type in self._initialized and self._initialized[chain_type]
    
    def get_blockchain_service(self, chain_type: BlockchainType) -> BlockchainService:
        """Get the blockchain service for a chain type."""
        if not self.is_registered(chain_type):
            raise ValueError(f"Blockchain {chain_type.value} is not registered")
        return self._blockchain_services[chain_type]
    
    def get_signature_service(self, chain_type: BlockchainType) -> SignatureService:
        """Get the signature service for a chain type."""
        if not self.is_registered(chain_type):
            raise ValueError(f"Blockchain {chain_type.value} is not registered")
        return self._signature_services[chain_type]
    
    def get_nonce_service(self, chain_type: BlockchainType) -> NonceService:
        """Get the nonce service for a chain type."""
        if not self.is_registered(chain_type):
            raise ValueError(f"Blockchain {chain_type.value} is not registered")
        return self._nonce_services[chain_type]
    
    def get_supported_chains(self) -> list[BlockchainType]:
        """Get list of registered/supported chains."""
        return [chain for chain, initialized in self._initialized.items() if initialized]
    
    async def disconnect_all(self) -> None:
        """Disconnect all blockchain services."""
        for service in self._blockchain_services.values():
            await service.disconnect()


# Global registry instance
blockchain_registry = BlockchainRegistry()


def register_chains() -> None:
    """
    Register all supported blockchain implementations.
    
    This function is called during application startup.
    Add new chain registrations here.
    """
    # Import and register Solana
    from app.blockchain.chains.solana import (
        SolanaBlockchainService,
        SolanaSignatureService,
        SolanaNonceService,
    )
    
    blockchain_registry.register(
        BlockchainType.SOLANA,
        blockchain_service=SolanaBlockchainService(),
        signature_service=SolanaSignatureService(),
        nonce_service=SolanaNonceService(),
    )
    
    # Future: Register Ethereum
    # from app.blockchain.chains.ethereum import (
    #     EthereumBlockchainService,
    #     EthereumSignatureService,
    #     EthereumNonceService,
    # )
    # blockchain_registry.register(
    #     BlockchainType.ETHEREUM,
    #     blockchain_service=EthereumBlockchainService(),
    #     signature_service=EthereumSignatureService(),
    #     nonce_service=EthereumNonceService(),
    # )
    
    # Future: Register Tron
    # from app.blockchain.chains.tron import (
    #     TronBlockchainService,
    #     TronSignatureService,
    #     TronNonceService,
    # )
    # blockchain_registry.register(
    #     BlockchainType.TRON,
    #     blockchain_service=TronBlockchainService(),
    #     signature_service=TronSignatureService(),
    #     nonce_service=TronNonceService(),
    # )
