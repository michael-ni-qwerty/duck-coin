"""
Solana blockchain implementation.

This module implements the blockchain interfaces for Solana:
- SolanaBlockchainService: RPC interactions and PDA derivation
- SolanaSignatureService: ed25519 signature generation
- SolanaNonceService: Nonce management with Redis + on-chain verification
"""

import base58
import struct
import time
from typing import Optional, Dict, Any, Tuple

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
import redis.asyncio as redis

from app.blockchain.base import (
    BlockchainType,
    BlockchainService,
    SignatureService,
    NonceService,
    PurchaseAuthorization,
    VestingInfo,
    PresaleConfig,
)
from app.core.config import settings


# Solana-specific constants (must match smart contract)
DOMAIN_SEPARATOR = b"PRESALE_V1"
PAYMENT_SOL = 0
PAYMENT_USDT = 1
PAYMENT_USDC = 2

# PDA Seeds
CONFIG_SEED = b"config"
VESTING_SEED = b"vesting"
NONCE_SEED = b"nonce"
VAULT_SEED = b"vault"


class SolanaBlockchainService(BlockchainService):
    """Solana blockchain service implementation."""
    
    def __init__(self):
        self._client: Optional[AsyncClient] = None
        self._program_id = Pubkey.from_string(settings.presale_program_id)
    
    @property
    def chain_type(self) -> BlockchainType:
        return BlockchainType.SOLANA
    
    @property
    def program_id(self) -> Pubkey:
        return self._program_id
    
    async def connect(self) -> None:
        if self._client is None:
            self._client = AsyncClient(settings.solana_rpc_url)
    
    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
    
    async def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.get_health()
            return True
        except Exception:
            return False
    
    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            await self.connect()
        return self._client
    
    def get_config_address(self) -> Tuple[str, Optional[int]]:
        pda, bump = Pubkey.find_program_address([CONFIG_SEED], self._program_id)
        return str(pda), bump
    
    def get_vesting_address(self, buyer: str) -> Tuple[str, Optional[int]]:
        buyer_pubkey = Pubkey.from_string(buyer)
        pda, bump = Pubkey.find_program_address(
            [VESTING_SEED, bytes(buyer_pubkey)],
            self._program_id
        )
        return str(pda), bump
    
    def get_nonce_address(self, buyer: str, nonce: int) -> Tuple[str, Optional[int]]:
        buyer_pubkey = Pubkey.from_string(buyer)
        nonce_bytes = struct.pack("<Q", nonce)
        pda, bump = Pubkey.find_program_address(
            [NONCE_SEED, bytes(buyer_pubkey), nonce_bytes],
            self._program_id
        )
        return str(pda), bump
    
    def _get_vault_address(self, config_pubkey: Pubkey) -> Tuple[str, int]:
        pda, bump = Pubkey.find_program_address(
            [VAULT_SEED, bytes(config_pubkey)],
            self._program_id
        )
        return str(pda), bump
    
    async def get_account_data(self, address: str) -> Optional[bytes]:
        client = await self._get_client()
        pubkey = Pubkey.from_string(address)
        response = await client.get_account_info(pubkey)
        if response.value is None:
            return None
        return response.value.data
    
    async def is_nonce_used(self, buyer: str, nonce: int) -> bool:
        nonce_address, _ = self.get_nonce_address(buyer, nonce)
        account_data = await self.get_account_data(nonce_address)
        if account_data is None:
            return False
        # Check is_used flag (after 8-byte discriminator)
        if len(account_data) > 8:
            return account_data[8] == 1
        return False
    
    async def get_vesting_info(self, wallet_address: str) -> Optional[VestingInfo]:
        vesting_address, _ = self.get_vesting_address(wallet_address)
        account_data = await self.get_account_data(vesting_address)
        
        if account_data is None:
            return VestingInfo(
                chain=BlockchainType.SOLANA,
                wallet_address=wallet_address,
                total_purchased=0,
                claimed_amount=0,
                vested_amount=0,
                claimable_amount=0,
                vesting_start_time=0,
                cliff_end_time=0,
                vesting_end_time=0,
                vesting_percentage=0.0,
            )
        
        # Parse vesting account data
        # Structure (after 8-byte discriminator):
        # - buyer: 32 bytes
        # - total_purchased: 8 bytes (u64)
        # - claimed_amount: 8 bytes (u64)
        # - bump: 1 byte
        if len(account_data) < 57:
            return None
        
        offset = 8 + 32  # Skip discriminator and buyer
        total_purchased = struct.unpack("<Q", account_data[offset:offset + 8])[0]
        offset += 8
        claimed_amount = struct.unpack("<Q", account_data[offset:offset + 8])[0]
        
        # Get vesting params from config
        config = await self.get_presale_config()
        if config:
            vesting_start_time = config.vesting_start_time
            cliff_duration = config.cliff_duration
            vesting_duration = config.vesting_duration
        else:
            vesting_start_time = 0
            cliff_duration = 0
            vesting_duration = 86400 * 365
        
        cliff_end_time = vesting_start_time + cliff_duration
        vesting_end_time = vesting_start_time + vesting_duration
        current_time = int(time.time())
        
        # Calculate vested amount
        if current_time < cliff_end_time:
            vested_amount = 0
        elif current_time >= vesting_end_time:
            vested_amount = total_purchased
        else:
            elapsed = current_time - cliff_end_time
            vesting_period = vesting_end_time - cliff_end_time
            vested_amount = (total_purchased * elapsed) // vesting_period if vesting_period > 0 else 0
        
        claimable_amount = max(0, vested_amount - claimed_amount)
        vesting_percentage = (vested_amount / total_purchased * 100) if total_purchased > 0 else 0.0
        
        return VestingInfo(
            chain=BlockchainType.SOLANA,
            wallet_address=wallet_address,
            total_purchased=total_purchased,
            claimed_amount=claimed_amount,
            vested_amount=vested_amount,
            claimable_amount=claimable_amount,
            vesting_start_time=vesting_start_time,
            cliff_end_time=cliff_end_time,
            vesting_end_time=vesting_end_time,
            vesting_percentage=round(vesting_percentage, 2),
        )
    
    async def get_presale_config(self) -> Optional[PresaleConfig]:
        config_address, _ = self.get_config_address()
        account_data = await self.get_account_data(config_address)
        
        if account_data is None:
            # Return default config from settings
            return PresaleConfig(
                chain=BlockchainType.SOLANA,
                program_id=settings.presale_program_id,
                presale_token_address=settings.presale_token_mint,
                treasury_address=settings.treasury_wallet,
                payment_tokens={
                    "SOL": None,
                    "USDT": settings.usdt_mint,
                    "USDC": settings.usdc_mint,
                },
                token_price_per_unit=0,
                cliff_duration=0,
                vesting_start_time=0,
                vesting_duration=0,
                is_active=True,
                total_sold=0,
            )
        
        # Parse config account - would need actual parsing based on account structure
        # For now, return settings-based config
        return PresaleConfig(
            chain=BlockchainType.SOLANA,
            program_id=settings.presale_program_id,
            presale_token_address=settings.presale_token_mint,
            treasury_address=settings.treasury_wallet,
            payment_tokens={
                "SOL": None,
                "USDT": settings.usdt_mint,
                "USDC": settings.usdc_mint,
            },
            token_price_per_unit=0,
            cliff_duration=0,
            vesting_start_time=0,
            vesting_duration=0,
            is_active=True,
            total_sold=0,
        )
    
    def get_pda_addresses(self, wallet_address: str) -> Dict[str, Dict[str, Any]]:
        config_address, config_bump = self.get_config_address()
        vesting_address, vesting_bump = self.get_vesting_address(wallet_address)
        
        config_pubkey = Pubkey.from_string(config_address)
        vault_address, vault_bump = self._get_vault_address(config_pubkey)
        
        return {
            "config": {"address": config_address, "bump": config_bump},
            "vesting": {"address": vesting_address, "bump": vesting_bump},
            "vault": {"address": vault_address, "bump": vault_bump},
        }


class SolanaSignatureService(SignatureService):
    """Solana ed25519 signature service implementation."""
    
    def __init__(self):
        self._keypair: Optional[Keypair] = None
        self._program_id = Pubkey.from_string(settings.presale_program_id)
    
    @property
    def chain_type(self) -> BlockchainType:
        return BlockchainType.SOLANA
    
    @property
    def keypair(self) -> Keypair:
        if self._keypair is None:
            if not settings.authorized_signer_private_key:
                raise ValueError("AUTHORIZED_SIGNER_PRIVATE_KEY not configured")
            secret_key = base58.b58decode(settings.authorized_signer_private_key)
            self._keypair = Keypair.from_bytes(secret_key)
        return self._keypair
    
    @property
    def signer_public_key(self) -> str:
        return str(self.keypair.pubkey())
    
    def get_payment_type_id(self, payment_type: str) -> int:
        mapping = {
            "SOL": PAYMENT_SOL,
            "USDT": PAYMENT_USDT,
            "USDC": PAYMENT_USDC,
        }
        return mapping.get(payment_type.upper(), PAYMENT_SOL)
    
    def get_payment_token_address(self, payment_type: str) -> Optional[str]:
        if payment_type.upper() == "SOL":
            return None
        elif payment_type.upper() == "USDT":
            return settings.usdt_mint
        elif payment_type.upper() == "USDC":
            return settings.usdc_mint
        return None
    
    def _get_payment_mint_pubkey(self, payment_type: str) -> Pubkey:
        address = self.get_payment_token_address(payment_type)
        if address is None:
            return Pubkey.default()
        return Pubkey.from_string(address)
    
    def construct_message(
        self,
        buyer: str,
        payment_token: Optional[str],
        payment_type: int,
        payment_amount: int,
        token_amount: int,
        nonce: int,
    ) -> bytes:
        """
        Construct the message to be signed.
        
        Message format (131 bytes total):
        - DOMAIN_SEPARATOR: 10 bytes
        - program_id: 32 bytes
        - buyer: 32 bytes
        - payment_mint: 32 bytes
        - payment_type: 1 byte
        - payment_amount: 8 bytes (little-endian u64)
        - token_amount: 8 bytes (little-endian u64)
        - nonce: 8 bytes (little-endian u64)
        """
        buyer_pubkey = Pubkey.from_string(buyer)
        payment_mint = Pubkey.from_string(payment_token) if payment_token else Pubkey.default()
        
        message = bytearray(131)
        offset = 0
        
        message[offset:offset + 10] = DOMAIN_SEPARATOR
        offset += 10
        
        message[offset:offset + 32] = bytes(self._program_id)
        offset += 32
        
        message[offset:offset + 32] = bytes(buyer_pubkey)
        offset += 32
        
        message[offset:offset + 32] = bytes(payment_mint)
        offset += 32
        
        message[offset] = payment_type
        offset += 1
        
        message[offset:offset + 8] = struct.pack("<Q", payment_amount)
        offset += 8
        
        message[offset:offset + 8] = struct.pack("<Q", token_amount)
        offset += 8
        
        message[offset:offset + 8] = struct.pack("<Q", nonce)
        
        return bytes(message)
    
    def sign_message(self, message: bytes) -> bytes:
        return self.keypair.sign_message(message)
    
    def generate_purchase_authorization(
        self,
        buyer_address: str,
        payment_type: str,
        payment_amount: int,
        token_amount: int,
        nonce: int,
    ) -> PurchaseAuthorization:
        payment_token = self.get_payment_token_address(payment_type)
        payment_type_id = self.get_payment_type_id(payment_type)
        
        message = self.construct_message(
            buyer=buyer_address,
            payment_token=payment_token,
            payment_type=payment_type_id,
            payment_amount=payment_amount,
            token_amount=token_amount,
            nonce=nonce,
        )
        
        signature = self.sign_message(message)
        
        return PurchaseAuthorization(
            chain=BlockchainType.SOLANA,
            buyer_address=buyer_address,
            payment_type=payment_type,
            payment_token_address=payment_token,
            payment_amount=payment_amount,
            token_amount=token_amount,
            nonce=nonce,
            signature=base58.b58encode(signature).decode("utf-8"),
            message=base58.b58encode(message).decode("utf-8"),
            signer_public_key=self.signer_public_key,
        )


class SolanaNonceService(NonceService):
    """Solana nonce service with Redis caching."""
    
    NONCE_PREFIX = "presale:solana:nonce:"
    NONCE_COUNTER_KEY = "presale:solana:nonce_counter"
    NONCE_TTL = 3600 * 24  # 24 hours
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._blockchain_service: Optional[SolanaBlockchainService] = None
    
    @property
    def chain_type(self) -> BlockchainType:
        return BlockchainType.SOLANA
    
    def set_blockchain_service(self, service: SolanaBlockchainService) -> None:
        """Set the blockchain service for on-chain verification."""
        self._blockchain_service = service
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    def _get_nonce_key(self, wallet: str, nonce: int) -> str:
        return f"{self.NONCE_PREFIX}{wallet}:{nonce}"
    
    async def generate_nonce(self, wallet: str) -> int:
        r = await self._get_redis()
        timestamp = int(time.time() * 1000)
        counter = await r.incr(self.NONCE_COUNTER_KEY)
        nonce = (timestamp << 20) | (counter & 0xFFFFF)
        
        key = self._get_nonce_key(wallet, nonce)
        await r.setex(key, self.NONCE_TTL, "pending")
        
        return nonce
    
    async def is_nonce_available(self, wallet: str, nonce: int) -> bool:
        r = await self._get_redis()
        key = self._get_nonce_key(wallet, nonce)
        
        status = await r.get(key)
        if status == "used":
            return False
        
        # Check on-chain if blockchain service is available
        if self._blockchain_service:
            is_used_onchain = await self._blockchain_service.is_nonce_used(wallet, nonce)
            if is_used_onchain:
                await r.setex(key, self.NONCE_TTL, "used")
                return False
        
        return True
    
    async def mark_nonce_pending(self, wallet: str, nonce: int) -> None:
        r = await self._get_redis()
        key = self._get_nonce_key(wallet, nonce)
        await r.setex(key, self.NONCE_TTL, "pending")
    
    async def mark_nonce_used(self, wallet: str, nonce: int) -> None:
        r = await self._get_redis()
        key = self._get_nonce_key(wallet, nonce)
        await r.setex(key, self.NONCE_TTL, "used")
