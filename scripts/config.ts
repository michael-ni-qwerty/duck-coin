import * as anchor from "@coral-xyz/anchor";
import { Keypair, LAMPORTS_PER_SOL, PublicKey, SYSVAR_RENT_PUBKEY, SystemProgram, Connection, clusterApiUrl } from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  getAccount,
  getOrCreateAssociatedTokenAccount,
  mintTo,
} from "@solana/spl-token";
import * as fs from "fs";
import * as path from "path";
const { transfer } = require("@solana/spl-token");


// Network Configuration
export const NETWORK: string = process.env.NETWORK || "devnet";

// Hardcoded Mint Addresses
export const DEVNET_MINT = new PublicKey("FdoibCPmzQm4Ps37GZdKC6CbSLo9HDmMh2Myb6Rf1tYd");
export const MAINNET_MINT = new PublicKey("BpfcMYvrrRweav64155uSkSnRVPnHK2ZKTXHb2kFiB1H");

export const TOKEN_MINT = NETWORK === "mainnet-beta" ? MAINNET_MINT : DEVNET_MINT;

// Test/Shared configuration
export const TOKEN_AMOUNT_RAW = 1_000_000_000n; // 1_000 tokens (6 decimals)
export const TEST_USER_SOL_TARGET = 0.1;
export const USD_AMOUNT = new anchor.BN("50000000"); // $50.00
export const GLOBAL_UNLOCK_TARGET = 10;
export const TARGET_TGE_PERCENTAGE = 30;


// Load the default Solana wallet for generic scripts
const homedir = require("os").homedir();
const walletFile = NETWORK === "mainnet-beta" ? "duck-coin-wallet.json" : "id.json";
const secretKeyString = fs.readFileSync(
  path.join(homedir, ".config", "solana", walletFile),
  "utf8"
);
export const payer = Keypair.fromSecretKey(Uint8Array.from(JSON.parse(secretKeyString)));

// Generic connection for non-Anchor scripts
export const connection = new Connection(
  NETWORK === "mainnet-beta" ? clusterApiUrl("mainnet-beta") : clusterApiUrl("devnet"),
  "confirmed"
);

export const idl = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../smart_contracts/target/idl/presale.json"),
    "utf8"
  )
);

// Explicit Program ID and Admin Wallet setup
export const PROGRAM_ID = new PublicKey("27bjcLeRgfnCAzfTDYgfxnWeuBTWUJeeEVf2RGcYD2B4");
export const ADMIN_WALLET = new anchor.Wallet(payer);

export const provider = new anchor.AnchorProvider(
  connection,
  ADMIN_WALLET,
  {
    ...anchor.AnchorProvider.defaultOptions(),
    commitment: "confirmed",
    preflightCommitment: "confirmed",
  }
);
anchor.setProvider(provider);

const programIdl = {
  ...idl,
  address: PROGRAM_ID.toBase58(),
};

export const program = new anchor.Program(programIdl, provider) as any;

// PDAs
export const [configPda] = PublicKey.findProgramAddressSync([Buffer.from("config")], program.programId);
export const [dailyStatePda] = PublicKey.findProgramAddressSync([Buffer.from("daily_state")], program.programId);
export const [vaultPda] = PublicKey.findProgramAddressSync([Buffer.from("vault"), configPda.toBuffer()], program.programId);

// Types
export type AllocationSnapshot = {
  amountPurchased: bigint;
  amountClaimed: bigint;
  claimableAmount: bigint;
  amountVesting: bigint;
  lastUnlockPct: number;
};

// Utility functions
export function assertEq(actual: bigint | number, expected: bigint | number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}. expected=${expected.toString()}, actual=${actual.toString()}`);
  }
}

export function logBalance(label: string, amount: bigint): void {
  console.log(`[BALANCE] ${label}: ${amount.toString()}`);
}

export async function confirmTx(signature: string): Promise<void> {
  const latestBlockhash = await provider.connection.getLatestBlockhash("confirmed");
  await provider.connection.confirmTransaction(
    {
      signature,
      blockhash: latestBlockhash.blockhash,
      lastValidBlockHeight: latestBlockhash.lastValidBlockHeight,
    },
    "confirmed"
  );
}

export async function fundTestUserIfNeeded(user: PublicKey, targetSol: number): Promise<void> {
  const targetLamports = BigInt(Math.floor(targetSol * LAMPORTS_PER_SOL));
  const currentLamports = BigInt(await provider.connection.getBalance(user));

  logBalance("Test user SOL before funding (lamports)", currentLamports);
  if (currentLamports >= targetLamports) {
    console.log(`test user already funded (>= ${targetSol} SOL)`);
    return;
  }

  const neededLamports = targetLamports - currentLamports;
  const tx = new anchor.web3.Transaction().add(
    SystemProgram.transfer({
      fromPubkey: ADMIN_WALLET.publicKey,
      toPubkey: user,
      lamports: Number(neededLamports),
    })
  );

  const sig = await anchor.web3.sendAndConfirmTransaction(
    provider.connection,
    tx,
    [ADMIN_WALLET.payer]
  );
  console.log(`funded test user with ${neededLamports.toString()} lamports. tx=${sig}`);

  const afterLamports = BigInt(await provider.connection.getBalance(user));
  logBalance("Test user SOL after funding (lamports)", afterLamports);
}

export async function ensureVaultLiquidity(minAmount: bigint): Promise<void> {
  console.log("\n--- ensure vault liquidity ---");
  const vaultBefore = await getAccount(provider.connection, vaultPda);
  logBalance("Vault sale-token before top-up", vaultBefore.amount);
  if (vaultBefore.amount >= minAmount) {
    console.log(`vault already funded. amount=${vaultBefore.amount.toString()}`);
    return;
  }

  const topUpAmount = minAmount - vaultBefore.amount;

  const mintSig = await mintTo(
    provider.connection,
    ADMIN_WALLET.payer,
    TOKEN_MINT,
    vaultPda,
    ADMIN_WALLET.payer,
    topUpAmount
  );
  console.log(`vault topped up by ${topUpAmount.toString()}. tx=${mintSig}`);
  const vaultAfter = await getAccount(provider.connection, vaultPda);
  logBalance("Vault sale-token after top-up", vaultAfter.amount);
}

export async function readAllocationSnapshot(allocationPda: PublicKey): Promise<AllocationSnapshot> {
  let allocation = await program.account.userAllocation.fetchNullable(allocationPda);
  for (let attempt = 0; !allocation && attempt < 5; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 400 * (attempt + 1)));
    allocation = await program.account.userAllocation.fetchNullable(allocationPda);
  }
  if (!allocation) {
    throw new Error(`Account does not exist or has no data ${allocationPda.toBase58()}`);
  }
  return {
    amountPurchased: BigInt(allocation.amountPurchased.toString()),
    amountClaimed: BigInt(allocation.amountClaimed.toString()),
    claimableAmount: BigInt(allocation.claimableAmount.toString()),
    amountVesting: BigInt(allocation.amountVesting.toString()),
    lastUnlockPct: Number(allocation.lastUnlockPct),
  };
}

export async function ensureUserAta(user: Keypair): Promise<PublicKey> {
  const ata = await getOrCreateAssociatedTokenAccount(
    provider.connection,
    user,
    TOKEN_MINT,
    user.publicKey
  );
  return ata.address;
}
