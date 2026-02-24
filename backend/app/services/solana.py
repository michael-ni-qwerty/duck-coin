"""
Solana service for interacting with the presale smart contract.

Handles calling credit_allocation on-chain after NOWPayments confirms payment.
"""

import base58
import base64
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
from app.api.presale_endpoints.common import validate_wallet_address

logger = logging.getLogger(__name__)

# PDA Seeds (must match smart contract constants)
CONFIG_SEED = b"config"
DAILY_STATE_SEED = b"daily_state"
ALLOCATION_SEED = b"allocation"
VAULT_SEED = b"vault"

# System program
SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")


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

    def build_identity_key(self, wallet_address: str) -> bytes:
        if not validate_wallet_address(wallet_address):
            raise ValueError("Unsupported wallet_address format. Expected Solana or EVM address.")
        normalized_wallet = wallet_address.strip().lower()
        preimage = normalized_wallet.encode("utf-8")
        return hashlib.sha256(preimage).digest()

    def get_allocation_pda(self, identity_key: bytes) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address(
            [ALLOCATION_SEED, identity_key], self._program_id
        )

    def get_vault_pda(self, config: Pubkey) -> tuple[Pubkey, int]:
        return Pubkey.find_program_address(
            [VAULT_SEED, bytes(config)], self._program_id
        )

    def get_associated_token_address(self, owner: Pubkey, mint: Pubkey) -> Pubkey:
        ata, _ = Pubkey.find_program_address(
            [bytes(owner), bytes(TOKEN_PROGRAM_ID), bytes(mint)],
            ASSOCIATED_TOKEN_PROGRAM_ID,
        )
        return ata

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
        global_unlock_pct = data[offset]
        offset += 1

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
            "global_unlock_pct": global_unlock_pct,
        }

    async def get_allocation_data(
        self,
        wallet_address: str,
    ) -> Optional[Dict[str, Any]]:
        """Read and parse an IdentityAllocation account."""
        client = await self._get_client()
        if not validate_wallet_address(wallet_address):
            raise ValueError("Unsupported wallet_address format. Expected Solana or EVM address.")

        identity_key = self.build_identity_key(wallet_address)
        alloc_pda, _ = self.get_allocation_pda(identity_key)
        resp = await client.get_account_info(alloc_pda)
        if resp.value is None:
            return None

        data = resp.value.data
        # Skip 8-byte discriminator
        # IdentityAllocation: amount_purchased(8) + amount_claimed(8) + claimable_amount(8)
        # + amount_vesting(8) + last_unlock_pct(1) + claim_authority(32)
        if len(data) < 73:
            return None

        offset = 8
        amount_purchased = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        amount_claimed = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        claimable_amount = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        amount_vesting = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        last_unlock_pct = data[offset]
        offset += 1
        claim_authority = str(Pubkey.from_bytes(data[offset : offset + 32]))

        return {
            "amount_purchased": amount_purchased,
            "amount_claimed": amount_claimed,
            "claimable_amount": claimable_amount,
            "amount_vesting": amount_vesting,
            "last_unlock_pct": last_unlock_pct,
            "claim_authority": claim_authority,
        }

    # --- On-chain writes ---

    async def credit_allocation(
        self,
        wallet_address: str,
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

        if not validate_wallet_address(wallet_address):
            raise ValueError("Unsupported wallet_address format. Expected Solana or EVM address.")

        identity_key = self.build_identity_key(wallet_address)
        config_pda, _ = self.get_config_pda()
        daily_state_pda, _ = self.get_daily_state_pda()
        alloc_pda, _ = self.get_allocation_pda(identity_key)

        # Build instruction data
        # Anchor discriminator for "credit_allocation" = first 8 bytes of SHA256("global:credit_allocation")
        discriminator = hashlib.sha256(b"global:credit_allocation").digest()[:8]

        # Encode args: identity_key([u8;32]) + token_amount(u64) + usd_amount(u64) + payment_id(String)
        payment_id_bytes = payment_id.encode("utf-8")
        ix_data = bytearray()
        ix_data.extend(discriminator)
        ix_data.extend(identity_key)                                # identity_key: [u8;32]
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
        logger.info(
            "credit_allocation tx sent: %s for wallet=%s",
            sig,
            wallet_address,
        )

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

    async def bind_claim_wallet(
        self,
        wallet_address: str,
        solana_wallet: str,
    ) -> str:
        """Call admin-only bind_claim_wallet instruction and return transaction signature."""
        client = await self._get_client()
        admin = self.admin_keypair

        try:
            solana_wallet_pk = Pubkey.from_string(solana_wallet)
        except Exception as e:
            raise ValueError(f"Invalid Solana wallet: {e}")

        if not validate_wallet_address(wallet_address):
            raise ValueError("Unsupported wallet_address format. Expected Solana or EVM address.")

        identity_key = self.build_identity_key(wallet_address)
        config_pda, _ = self.get_config_pda()
        user_allocation_pda, _ = self.get_allocation_pda(identity_key)

        discriminator = hashlib.sha256(b"global:bind_claim_wallet").digest()[:8]
        ix_data = bytearray()
        ix_data.extend(discriminator)
        ix_data.extend(identity_key)
        ix_data.extend(bytes(solana_wallet_pk))

        accounts = [
            AccountMeta(pubkey=config_pda, is_signer=False, is_writable=False),
            AccountMeta(pubkey=user_allocation_pda, is_signer=False, is_writable=True),
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
        await client.confirm_transaction(resp.value, commitment="confirmed")

        logger.info(
            "bind_claim_wallet tx confirmed: %s for wallet=%s to solana_wallet=%s",
            sig,
            wallet_address,
            solana_wallet_pk,
        )

        return sig

    async def prepare_claim_payload(
        self,
        wallet_address: str,
        user_wallet: str,
        user_token_account: Optional[str],
    ) -> Dict[str, str]:
        """
        Prepare unsigned claim transaction payload for user-side signing.

        Returns dict: user_wallet, recent_blockhash, unsigned_tx_base64.
        """
        client = await self._get_client()

        try:
            user_pubkey = Pubkey.from_string(user_wallet)
        except Exception as e:
            raise ValueError(f"Invalid user wallet: {e}")

        config_data = await self.get_config_data()
        if config_data is None:
            raise ValueError("Presale config not found on-chain")

        if not validate_wallet_address(wallet_address):
            raise ValueError("Unsupported wallet_address format. Expected Solana or EVM address.")

        token_mint = Pubkey.from_string(config_data["token_mint"])
        identity_key = self.build_identity_key(wallet_address)
        allocation_data = await self.get_allocation_data(wallet_address)
        if allocation_data is None:
            raise ValueError("No allocation found for this identity")

        claim_authority = allocation_data["claim_authority"]
        if claim_authority == str(Pubkey.default()):
            raise ValueError("Claim wallet is not bound yet. Bind it before claiming.")
        if claim_authority != str(user_pubkey):
            raise ValueError("Provided Solana wallet does not match bound claim wallet")

        if user_token_account:
            try:
                user_token_account_pk = Pubkey.from_string(user_token_account)
            except Exception as e:
                raise ValueError(f"Invalid user token account: {e}")
        else:
            user_token_account_pk = self.get_associated_token_address(user_pubkey, token_mint)

        config_pda, _ = self.get_config_pda()
        user_allocation_pda, _ = self.get_allocation_pda(identity_key)
        vault_pda, _ = self.get_vault_pda(config_pda)

        discriminator = hashlib.sha256(b"global:claim").digest()[:8]
        ix_data = bytearray()
        ix_data.extend(discriminator)
        ix_data.extend(identity_key)

        accounts = [
            AccountMeta(pubkey=config_pda, is_signer=False, is_writable=False),
            AccountMeta(pubkey=user_allocation_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_pubkey, is_signer=True, is_writable=True),
            AccountMeta(pubkey=vault_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_token_account_pk, is_signer=False, is_writable=True),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        ix = Instruction(self._program_id, bytes(ix_data), accounts)

        blockhash_resp = await client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash([ix], user_pubkey, recent_blockhash)
        tx = Transaction.new_unsigned(msg)
        unsigned_tx_base64 = base64.b64encode(bytes(tx)).decode("utf-8")

        logger.info(f"Prepared unsigned claim payload for user={user_pubkey}")

        return {
            "user_wallet": str(user_pubkey),
            "user_token_account": str(user_token_account_pk),
            "recent_blockhash": str(recent_blockhash),
            "unsigned_tx_base64": unsigned_tx_base64,
        }


# Singleton instance
solana_service = SolanaService()
