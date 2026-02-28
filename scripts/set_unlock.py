#!/usr/bin/env python3
"""
set_unlock.py — Call the set_unlock instruction on the presale program.

Sets the global vesting unlock percentage. Can only increase, max 100.
Must be called by the admin wallet.

Usage:
    python scripts/set_unlock.py <unlock_pct> [--cluster CLUSTER]

Examples:
    python scripts/set_unlock.py 25
    python scripts/set_unlock.py 50 --cluster devnet
    python scripts/set_unlock.py 100 --cluster mainnet
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solana.transaction import Transaction
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import base58
import hashlib

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# ── Constants (must match on-chain) ────────────────────────────
SEED_CONFIG = b"config"

# ── Cluster config ─────────────────────────────────────────────
CLUSTERS = {
    "localnet": "http://localhost:8899",
    "devnet": "https://api.devnet.solana.com",
    "mainnet": "https://api.mainnet-beta.solana.com",
}

# ── Colors ─────────────────────────────────────────────────────
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{CYAN}[set_unlock]{NC} {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[  ok  ]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[error ]{NC} {msg}", file=sys.stderr)


def load_env() -> None:
    """Load .env from project root or backend."""
    for env_path in (PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"):
        if env_path.exists():
            load_dotenv(env_path)
            return
    err("No .env file found. Copy .env.example to .env and fill in values.")
    sys.exit(1)


def get_admin_keypair() -> Keypair:
    """Load admin keypair from ADMIN_PRIVATE_KEY env var."""
    private_key = os.environ.get("ADMIN_PRIVATE_KEY", "")
    if not private_key or private_key == "YourBase58EncodedAdminPrivateKeyHere":
        err("ADMIN_PRIVATE_KEY not set in .env")
        sys.exit(1)

    try:
        secret = base58.b58decode(private_key)
        return Keypair.from_bytes(secret)
    except Exception as e:
        err(f"Invalid ADMIN_PRIVATE_KEY: {e}")
        sys.exit(1)


def get_program_id() -> Pubkey:
    """Load program ID from env or Anchor.toml."""
    program_id_str = os.environ.get("PRESALE_PROGRAM_ID", "")
    if not program_id_str:
        err("PRESALE_PROGRAM_ID not set in .env")
        sys.exit(1)

    try:
        return Pubkey.from_string(program_id_str)
    except Exception as e:
        err(f"Invalid PRESALE_PROGRAM_ID: {e}")
        sys.exit(1)


def derive_config_pda(program_id: Pubkey) -> tuple[Pubkey, int]:
    """Derive the config PDA address."""
    return Pubkey.find_program_address([SEED_CONFIG], program_id)


def build_set_unlock_ix(
    program_id: Pubkey,
    config_pda: Pubkey,
    admin: Pubkey,
    unlock_pct: int,
) -> Instruction:
    """Build the set_unlock instruction."""
    # Anchor discriminator: first 8 bytes of sha256("global:set_unlock")
    discriminator = hashlib.sha256(b"global:set_unlock").digest()[:8]

    # Instruction data: discriminator + unlock_pct (u8)
    data = discriminator + unlock_pct.to_bytes(1, "little")

    accounts = [
        AccountMeta(pubkey=config_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=admin, is_signer=True, is_writable=False),
    ]

    return Instruction(program_id, data, accounts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Set global vesting unlock percentage")
    parser.add_argument(
        "unlock_pct", type=int, help="Unlock percentage (0-100, can only increase)"
    )
    parser.add_argument(
        "--cluster", default="devnet", choices=CLUSTERS.keys(), help="Solana cluster"
    )
    args = parser.parse_args()

    # Validate
    if args.unlock_pct < 0 or args.unlock_pct > 100:
        err("unlock_pct must be between 0 and 100")
        sys.exit(1)

    load_env()

    # Setup
    rpc_url = os.environ.get("SOLANA_RPC_URL", CLUSTERS[args.cluster])
    client = Client(rpc_url, commitment=Confirmed)
    admin = get_admin_keypair()
    program_id = get_program_id()
    config_pda, _ = derive_config_pda(program_id)

    log(f"Cluster:     {YELLOW}{args.cluster}{NC} ({rpc_url})")
    log(f"Program ID:  {YELLOW}{program_id}{NC}")
    log(f"Config PDA:  {config_pda}")
    log(f"Admin:       {admin.pubkey()}")
    log(f"Unlock pct:  {YELLOW}{args.unlock_pct}%{NC}")

    # Build and send transaction
    ix = build_set_unlock_ix(program_id, config_pda, admin.pubkey(), args.unlock_pct)

    recent_blockhash = client.get_latest_blockhash(Confirmed).value.blockhash
    tx = Transaction.new_signed_with_payer(
        [ix],
        admin.pubkey(),
        [admin],
        recent_blockhash,
    )

    log("Sending transaction...")
    try:
        result = client.send_transaction(tx)
        sig = result.value
        ok(f"Transaction sent: {YELLOW}{sig}{NC}")
        log(f"Explorer: https://explorer.solana.com/tx/{sig}?cluster={args.cluster}")
    except Exception as e:
        err(f"Transaction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
