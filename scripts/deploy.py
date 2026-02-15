#!/usr/bin/env python3
"""
deploy.py — Build, deploy, and initialize the presale program.

Usage:
    python scripts/deploy.py [CLUSTER]

CLUSTER: localnet (default) | devnet | mainnet

Environment variables (optional):
    TOKEN_MINT        — SPL token mint address (required for initialize)
    PRESALE_START     — Unix timestamp for presale start (default: now + 1 day)
    SKIP_INIT         — Set to "true" to skip the initialize step
"""

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SC_DIR = PROJECT_ROOT / "smart_contracts"
LIB_RS = SC_DIR / "programs" / "presale" / "src" / "lib.rs"
ANCHOR_TOML = SC_DIR / "Anchor.toml"
PROGRAM_SO = SC_DIR / "target" / "deploy" / "presale.so"
PROGRAM_KEYPAIR = SC_DIR / "target" / "deploy" / "presale-keypair.json"

# ── Cluster config ─────────────────────────────────────────────
CLUSTERS = {
    "localnet": "http://localhost:8899",
    "devnet": "https://api.devnet.solana.com",
    "mainnet": "https://api.mainnet-beta.solana.com",
}

# ── Colors ─────────────────────────────────────────────────────
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{CYAN}[deploy]{NC} {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[  ok  ]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[ warn ]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[error ]{NC} {msg}", file=sys.stderr)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        err(f"Command failed: {' '.join(cmd)}")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def ensure_path() -> None:
    """Add solana and anchor to PATH if not already present."""
    solana_bin = Path.home() / ".local" / "share" / "solana" / "install" / "active_release" / "bin"
    avm_bin = Path.home() / ".avm" / "bin"
    extra = f"{solana_bin}:{avm_bin}"
    if str(solana_bin) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{extra}:{os.environ['PATH']}"


# ── Steps ──────────────────────────────────────────────────────

def check_prerequisites() -> None:
    log("Checking prerequisites...")
    ensure_path()

    for cmd in ("solana", "anchor"):
        if not shutil.which(cmd):
            err(f"{cmd} is not installed. Aborting.")
            sys.exit(1)

    solana_ver = run(["solana", "--version"]).stdout.strip()
    anchor_ver = run(["anchor", "--version"]).stdout.strip()
    ok(solana_ver)
    ok(anchor_ver)


def configure_cluster(cluster: str) -> str:
    if cluster not in CLUSTERS:
        err(f"Unknown cluster: {cluster}. Use: {', '.join(CLUSTERS)}")
        sys.exit(1)

    rpc_url = CLUSTERS[cluster]
    run(["solana", "config", "set", "--url", rpc_url])
    log(f"Cluster: {YELLOW}{cluster}{NC} ({rpc_url})")
    return rpc_url


def check_wallet(cluster: str) -> str:
    result = run(["solana", "config", "get", "keypair"], check=False)
    wallet_path = result.stdout.strip().split()[-1] if result.stdout.strip() else ""

    if not wallet_path or not Path(wallet_path).exists():
        err(f"Wallet keypair not found at {wallet_path}")
        err("Run: solana-keygen new -o ~/.config/solana/id.json")
        sys.exit(1)

    admin_pubkey = run(["solana", "address"]).stdout.strip()
    log(f"Admin wallet: {YELLOW}{admin_pubkey}{NC}")

    # Check balance (skip for localnet)
    if cluster != "localnet":
        balance_result = run(["solana", "balance", "--lamports"], check=False)
        try:
            balance = int(balance_result.stdout.strip().split()[0])
        except (ValueError, IndexError):
            balance = 0

        if balance < 1_000_000_000:
            warn(f"Low balance: {balance / 1e9:.4f} SOL. You may need SOL for deployment.")
            if cluster == "devnet":
                log("Requesting airdrop...")
                airdrop = run(["solana", "airdrop", "2"], check=False)
                if airdrop.returncode != 0:
                    warn("Airdrop failed — you may need to fund manually.")

    return admin_pubkey


def build() -> None:
    log("Building smart contract...")
    result = run(["anchor", "build"], cwd=SC_DIR)
    # Print last 5 lines of output
    lines = (result.stdout + result.stderr).strip().splitlines()
    for line in lines[-5:]:
        print(f"  {line}")

    if not PROGRAM_SO.exists():
        err(f"Build failed — {PROGRAM_SO} not found.")
        sys.exit(1)

    size_mb = PROGRAM_SO.stat().st_size / (1024 * 1024)
    ok(f"Build complete: {size_mb:.1f} MB")


def get_program_id() -> str:
    # Generate keypair if missing
    if not PROGRAM_KEYPAIR.exists():
        log("Generating program keypair...")
        PROGRAM_KEYPAIR.parent.mkdir(parents=True, exist_ok=True)
        run(["solana-keygen", "new", "--no-bip39-passphrase", "-o", str(PROGRAM_KEYPAIR)])

    program_id = run(["solana-keygen", "pubkey", str(PROGRAM_KEYPAIR)]).stdout.strip()
    log(f"Program ID: {YELLOW}{program_id}{NC}")
    return program_id


def sync_program_id(program_id: str) -> None:
    """Update declare_id! in lib.rs and Anchor.toml if they don't match."""
    lib_content = LIB_RS.read_text()
    match = re.search(r'declare_id!\("([^"]+)"\)', lib_content)
    if not match:
        err("Could not find declare_id! in lib.rs")
        sys.exit(1)

    current_id = match.group(1)
    if current_id == program_id:
        return

    warn(f"Updating declare_id! in lib.rs: {current_id} -> {program_id}")

    # Update lib.rs
    new_content = lib_content.replace(f'declare_id!("{current_id}")', f'declare_id!("{program_id}")')
    LIB_RS.write_text(new_content)

    # Update Anchor.toml
    anchor_content = ANCHOR_TOML.read_text()
    anchor_content = anchor_content.replace(current_id, program_id)
    ANCHOR_TOML.write_text(anchor_content)

    log("Rebuilding with updated program ID...")
    run(["anchor", "build"], cwd=SC_DIR)
    ok("Rebuild complete")


def start_local_validator() -> int | None:
    """Start a local validator if not already running."""
    check = run(["solana", "cluster-version"], check=False)
    if check.returncode == 0:
        return None

    warn("Local validator not running. Starting one...")
    proc = subprocess.Popen(
        ["solana-test-validator", "--reset", "--quiet"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    log(f"Validator started (PID: {proc.pid})")
    return proc.pid


def deploy(cluster: str) -> None:
    if cluster == "mainnet":
        print()
        warn("You are about to deploy to MAINNET.")
        confirm = input("Type 'yes' to confirm: ").strip()
        if confirm != "yes":
            err("Deployment cancelled.")
            sys.exit(1)

    if cluster == "localnet":
        start_local_validator()

    log(f"Deploying to {cluster}...")
    result = run(["anchor", "deploy", "--provider.cluster", cluster], cwd=SC_DIR)
    lines = (result.stdout + result.stderr).strip().splitlines()
    for line in lines[-5:]:
        print(f"  {line}")

    ok(f"Program deployed to {GREEN}{cluster}{NC}")


def initialize(cluster: str, program_id: str) -> None:
    skip_init = os.environ.get("SKIP_INIT", "false").lower() == "true"
    if skip_init:
        warn("Skipping initialization (SKIP_INIT=true)")
        return

    token_mint = os.environ.get("TOKEN_MINT", "")
    if not token_mint:
        warn("TOKEN_MINT not set. Skipping initialization.")
        warn("  To initialize, run:")
        warn(f"  TOKEN_MINT=<mint_address> python scripts/deploy.py {cluster}")
        return

    default_start = int(time.time()) + 86400
    start_time = int(os.environ.get("PRESALE_START", default_start))
    start_dt = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat()

    log("Initializing presale program...")
    log(f"  Token mint:  {token_mint}")
    log(f"  Start time:  {start_time} ({start_dt})")

    idl_path = SC_DIR / "target" / "idl" / "presale.json"
    if idl_path.exists():
        print()
        log("Run the following to upload the IDL:")
        print(f"  anchor idl init --filepath {idl_path} {program_id}")
        print()


def print_summary(cluster: str, rpc_url: str, program_id: str, admin_pubkey: str) -> None:
    print()
    print("==========================================")
    print(f" {GREEN}Deployment Summary{NC}")
    print("==========================================")
    print(f" Cluster:    {YELLOW}{cluster}{NC}")
    print(f" Program ID: {YELLOW}{program_id}{NC}")
    print(f" Admin:      {YELLOW}{admin_pubkey}{NC}")
    print(f" Binary:     {PROGRAM_SO}")
    print("==========================================")
    print()
    print(" Update your backend .env:")
    print(f"   PRESALE_PROGRAM_ID={program_id}")
    print(f"   SOLANA_RPC_URL={rpc_url}")
    print()


# ── Main ───────────────────────────────────────────────────────

def main() -> None:
    cluster = sys.argv[1] if len(sys.argv) > 1 else "localnet"

    check_prerequisites()
    rpc_url = configure_cluster(cluster)
    admin_pubkey = check_wallet(cluster)
    build()
    program_id = get_program_id()
    sync_program_id(program_id)
    deploy(cluster)
    initialize(cluster, program_id)
    print_summary(cluster, rpc_url, program_id, admin_pubkey)


if __name__ == "__main__":
    main()
