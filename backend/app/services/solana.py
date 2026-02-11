"""
Solana service for interacting with the presale smart contract.

Handles calling credit_allocation on-chain after NOWPayments confirms payment.
"""

import base58
import hashlib
import logging
import struct
from typing import Optional, Dict, Any

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message
from solana.rpc.async_api import AsyncClient
from app.core.config import settings

logger = logging.getLogger(__name__)

# PDA Seeds (must match smart contract constants)
CONFIG_SEED = b"config"
DAILY_STATE_SEED = b"daily_state"
ALLOCATION_SEED = b"allocation"
VAULT_SEED = b"vault"

# System program
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")


class SolanaService:
    """Service for interacting with the presale program on Solana."""

    def __init__(self):
        self._client: Optional[AsyncClient] = None
        self._keypair: Optional[Keypair] = None
        self._program_id = Pubkey.from_string(settings.presale_program_id)

    @property
    def program_id(self) -> Pubkey:
        return self._program_id

    @property
    def admin_keypair(self) -> Keypair:
        if self._keypair is None:
            if not settings.admin_private_key:
                raise ValueError("ADMIN_PRIVATE_KEY not configured")
            secret_key = base58.b58decode(settings.admin_private_key)
            self._keypair = Keypair.from_bytes(secret_key)
        return self._keypair

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(settings.solana_rpc_url)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def is_connected(self) -> bool:
        try:
            client = await self._get_client()
            await client.get_health()
            return True
        except Exception:
            return False

    # --- PDA derivation ---

    def get_config_pda(self) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address([CONFIG_SEED], self._program_id)

    def get_daily_state_pda(self) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address([DAILY_STATE_SEED], self._program_id)

    def get_allocation_pda(self, user: Pubkey) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address(
            [ALLOCATION_SEED, bytes(user)], self._program_id
        )

    def get_vault_pda(self, config: Pubkey) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address(
            [VAULT_SEED, bytes(config)], self._program_id
        )

    # --- On-chain reads ---

    async def get_config_data(self) -> Optional[Dict[str, Any]]:
        """Read and parse the PresaleConfig account."""
        client = await self._get_client()
        config_pda, _ = self.get_config_pda()
        resp = await client.get_account_info(config_pda)
        if resp.value is None:
            return None

        data = resp.value.data
        if len(data) < 8:
            return None

        # Skip 8-byte Anchor discriminator
        offset = 8
        admin = Pubkey.from_bytes(data[offset : offset + 32])
        offset += 32
        token_mint = Pubkey.from_bytes(data[offset : offset + 32])
        offset += 32
        token_price_usd = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        tge_percentage = data[offset]
        offset += 1
        start_time = struct.unpack_from("<q", data, offset)[0]
        offset += 8
        daily_cap = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        total_sold = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        presale_supply = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        total_burned = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        status_byte = data[offset]
        offset += 1
        total_raised_usd = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        sold_today = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        status_map = {0: "PresaleActive", 1: "PresaleEnded", 2: "TokenLaunched"}

        return {
            "admin": str(admin),
            "token_mint": str(token_mint),
            "token_price_usd": token_price_usd,
            "tge_percentage": tge_percentage,
            "start_time": start_time,
            "daily_cap": daily_cap,
            "total_sold": total_sold,
            "presale_supply": presale_supply,
            "total_burned": total_burned,
            "status": status_map.get(status_byte, "Unknown"),
            "total_raised_usd": total_raised_usd,
            "sold_today": sold_today,
        }

    async def get_allocation_data(self, user_pubkey: str) -> Optional[Dict[str, Any]]:
        """Read and parse a UserAllocation account."""
        client = await self._get_client()
        user = Pubkey.from_string(user_pubkey)
        alloc_pda, _ = self.get_allocation_pda(user)
        resp = await client.get_account_info(alloc_pda)
        if resp.value is None:
            return None

        data = resp.value.data
        # Skip 8-byte discriminator
        # UserAllocation: amount_purchased(8) + amount_claimed(8) + claimable_amount(8)
        if len(data) < 32:
            return None

        offset = 8
        amount_purchased = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        amount_claimed = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        claimable_amount = struct.unpack_from("<Q", data, offset)[0]

        return {
            "amount_purchased": amount_purchased,
            "amount_claimed": amount_claimed,
            "claimable_amount": claimable_amount,
        }

    # --- On-chain writes ---

    async def credit_allocation(
        self,
        user_pubkey_str: str,
        token_amount: int,
        usd_amount: int,
        payment_id: str,
    ) -> str:
        """
        Call the credit_allocation instruction on the presale program.

        Returns the transaction signature.
        """
        client = await self._get_client()
        admin = self.admin_keypair

        user_pubkey = Pubkey.from_string(user_pubkey_str)
        config_pda, _ = self.get_config_pda()
        daily_state_pda, _ = self.get_daily_state_pda()
        alloc_pda, _ = self.get_allocation_pda(user_pubkey)

        # Build instruction data
        # Anchor discriminator for "credit_allocation" = first 8 bytes of SHA256("global:credit_allocation")
        discriminator = hashlib.sha256(b"global:credit_allocation").digest()[:8]

        # Encode args: user(Pubkey) + token_amount(u64) + usd_amount(u64) + payment_id(String)
        payment_id_bytes = payment_id.encode("utf-8")
        ix_data = bytearray()
        ix_data.extend(discriminator)
        ix_data.extend(bytes(user_pubkey))                          # user: Pubkey
        ix_data.extend(struct.pack("<Q", token_amount))             # token_amount: u64
        ix_data.extend(struct.pack("<Q", usd_amount))               # usd_amount: u64
        ix_data.extend(struct.pack("<I", len(payment_id_bytes)))    # String length prefix
        ix_data.extend(payment_id_bytes)                            # String data

        accounts = [
            AccountMeta(pubkey=config_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=daily_state_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=alloc_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=admin.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        ix = Instruction(self._program_id, bytes(ix_data), accounts)

        # Get recent blockhash
        blockhash_resp = await client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash([ix], admin.pubkey(), recent_blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([admin], recent_blockhash)

        # Send transaction
        resp = await client.send_transaction(tx)
        sig = str(resp.value)
        logger.info(f"credit_allocation tx sent: {sig} for user={user_pubkey_str}")

        # Confirm
        await client.confirm_transaction(resp.value, commitment="confirmed")
        logger.info(f"credit_allocation tx confirmed: {sig}")

        return sig


    async def update_config(
        self,
        new_price: int,
        new_tge: int,
        new_daily_cap: int,
    ) -> str:
        """
        Call the update_config instruction on the presale program.

        This triggers the daily rollover: burns unsold tokens from the previous day,
        resets sold_today to 0, and advances current_day.

        Pass the current on-chain values to keep config unchanged while still
        triggering the rollover logic.

        Returns the transaction signature.
        """
        client = await self._get_client()
        admin = self.admin_keypair

        config_pda, _ = self.get_config_pda()
        daily_state_pda, _ = self.get_daily_state_pda()

        # Anchor discriminator for "update_config"
        discriminator = hashlib.sha256(b"global:update_config").digest()[:8]

        # Encode args: new_price(u64) + new_tge(u8) + new_daily_cap(u64)
        ix_data = bytearray()
        ix_data.extend(discriminator)
        ix_data.extend(struct.pack("<Q", new_price))       # new_price: u64
        ix_data.append(new_tge)                              # new_tge: u8
        ix_data.extend(struct.pack("<Q", new_daily_cap))    # new_daily_cap: u64

        accounts = [
            AccountMeta(pubkey=config_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=daily_state_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=admin.pubkey(), is_signer=True, is_writable=False),
        ]

        ix = Instruction(self._program_id, bytes(ix_data), accounts)

        blockhash_resp = await client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash([ix], admin.pubkey(), recent_blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([admin], recent_blockhash)

        resp = await client.send_transaction(tx)
        sig = str(resp.value)
        logger.info(f"update_config tx sent: {sig}")

        await client.confirm_transaction(resp.value, commitment="confirmed")
        logger.info(f"update_config tx confirmed: {sig}")

        return sig


# Singleton instance
solana_service = SolanaService()
