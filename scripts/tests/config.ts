// Shared configuration and utilities for presale tests

import * as anchor from "@coral-xyz/anchor";
import { Keypair, LAMPORTS_PER_SOL, PublicKey, SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  getAccount,
  getOrCreateAssociatedTokenAccount,
  mintTo,
} from "@solana/spl-token";
import * as fs from "fs";

// Test configuration
export const TOKEN_MINT = new PublicKey("6YskGKuqzVX9rjxvWkvN3vUC5BH6rZ7faKgzzWjdmLca");
export const PAYMENT_MINT = new PublicKey("B9xhegJm4vCmzHBm6cgQxRyqVnxRubBgTR953dKJUvQy");
export const TOKEN_AMOUNT_RAW = 1_000_000_000_000n; // 1000 tokens (9 decimals)
export const PAYMENT_AMOUNT_RAW = 50_000_000n; // 50.000000 payment tokens (6 decimals)
export const TEST_USER_SOL_TARGET = 0.1;
export const USD_AMOUNT = new anchor.BN("50000000"); // $50.00
export const GLOBAL_UNLOCK_TARGET = 10;
export const TARGET_TGE_PERCENTAGE = 30;

// Provider and program setup
export const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);

export const idl = JSON.parse(
  fs.readFileSync(
    "/home/michael/Desktop/my/duck-coin/smart_contracts/target/idl/presale.json",
    "utf8"
  )
);
export const program = new anchor.Program(idl, provider) as any;
export const ADMIN_WALLET = provider.wallet;

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
  const allocation = await program.account.userAllocation.fetch(allocationPda);
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
