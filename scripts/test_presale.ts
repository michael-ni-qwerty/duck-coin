// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/test_presale.ts

import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Keypair, LAMPORTS_PER_SOL, PublicKey, SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  getAccount,
  getOrCreateAssociatedTokenAccount,
  mintTo,
  transfer,
} from "@solana/spl-token";
import * as fs from "fs";

const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);

const idl = JSON.parse(
  fs.readFileSync(
    "/home/michael/Desktop/my/duck-coin/smart_contracts/target/idl/presale.json",
    "utf8"
  )
);
const program = new Program(idl, provider) as any;

const TOKEN_MINT = new PublicKey("6YskGKuqzVX9rjxvWkvN3vUC5BH6rZ7faKgzzWjdmLca");
const PAYMENT_MINT = new PublicKey("B9xhegJm4vCmzHBm6cgQxRyqVnxRubBgTR953dKJUvQy");
const ADMIN_WALLET = provider.wallet;
const TOKEN_AMOUNT_RAW = 1_000_000_000_000n; // 1000 tokens (9 decimals)
const PAYMENT_AMOUNT_RAW = 50_000_000n; // 50.000000 payment tokens (6 decimals)
const TEST_USER_SOL_TARGET = 0.1;
const USD_AMOUNT = new anchor.BN("50000000"); // $50.00
const GLOBAL_UNLOCK_TARGET = 10;
const TARGET_TGE_PERCENTAGE = 30;

const [configPda] = PublicKey.findProgramAddressSync([Buffer.from("config")], program.programId);
const [dailyStatePda] = PublicKey.findProgramAddressSync([Buffer.from("daily_state")], program.programId);
const [vaultPda] = PublicKey.findProgramAddressSync([Buffer.from("vault"), configPda.toBuffer()], program.programId);

type AllocationSnapshot = {
  amountPurchased: bigint;
  amountClaimed: bigint;
  claimableAmount: bigint;
  amountVesting: bigint;
  lastUnlockPct: number;
};

function assertEq(actual: bigint | number, expected: bigint | number, message: string): void {
  if (actual !== expected) {
    throw new Error(`${message}. expected=${expected.toString()}, actual=${actual.toString()}`);
  }
}

function logBalance(label: string, amount: bigint): void {
  console.log(`[BALANCE] ${label}: ${amount.toString()}`);
}

async function preparePaymentAndSimulatePurchase(buyer: Keypair): Promise<void> {
  console.log("\n--- 3) simulate buyer payment token transfer ---");

  const buyerPaymentAta = await getOrCreateAssociatedTokenAccount(
    provider.connection,
    buyer,
    PAYMENT_MINT,
    buyer.publicKey
  );
  const adminPaymentAta = await getOrCreateAssociatedTokenAccount(
    provider.connection,
    ADMIN_WALLET.payer,
    PAYMENT_MINT,
    ADMIN_WALLET.publicKey
  );

  const buyerBeforeFunding = await getAccount(provider.connection, buyerPaymentAta.address);
  logBalance("Buyer payment ATA before funding", buyerBeforeFunding.amount);
  if (buyerBeforeFunding.amount < PAYMENT_AMOUNT_RAW) {
    const topUpAmount = PAYMENT_AMOUNT_RAW - buyerBeforeFunding.amount;
    const mintSig = await mintTo(
      provider.connection,
      buyer,
      PAYMENT_MINT,
      buyerPaymentAta.address,
      ADMIN_WALLET.payer,
      topUpAmount
    );
    console.log(`buyer payment ATA topped up by ${topUpAmount.toString()}. tx=${mintSig}`);
  }

  const buyerBefore = await getAccount(provider.connection, buyerPaymentAta.address);
  const adminBefore = await getAccount(provider.connection, adminPaymentAta.address);
  logBalance("Buyer payment ATA before transfer", buyerBefore.amount);
  logBalance("Admin payment ATA before transfer", adminBefore.amount);

  const transferSig = await transfer(
    provider.connection,
    buyer,
    buyerPaymentAta.address,
    adminPaymentAta.address,
    buyer,
    PAYMENT_AMOUNT_RAW
  );
  console.log(`payment transfer tx=${transferSig} (payer=test user)`);

  const buyerAfter = await getAccount(provider.connection, buyerPaymentAta.address);
  const adminAfter = await getAccount(provider.connection, adminPaymentAta.address);
  logBalance("Buyer payment ATA after transfer", buyerAfter.amount);
  logBalance("Admin payment ATA after transfer", adminAfter.amount);

  assertEq(buyerBefore.amount - buyerAfter.amount, PAYMENT_AMOUNT_RAW, "buyer payment debit mismatch");
  assertEq(adminAfter.amount - adminBefore.amount, PAYMENT_AMOUNT_RAW, "admin payment credit mismatch");
  console.log("payment token transfer assertions passed");
}

async function fundTestUserIfNeeded(user: PublicKey, targetSol: number): Promise<void> {
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

async function initializePresale(): Promise<void> {
  console.log("\n--- 1) initialize presale ---");
  const startTime = new anchor.BN(Math.floor(Date.now() / 1000) - 3600);
  try {
    const tx = await program.methods
      .initialize(startTime)
      .accounts({
        config: configPda,
        dailyState: dailyStatePda,
        admin: ADMIN_WALLET.publicKey,
        tokenMint: TOKEN_MINT,
        vaultTokenAccount: vaultPda,
        systemProgram: SystemProgram.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
        rent: SYSVAR_RENT_PUBKEY,
      })
      .rpc();
    console.log(`initialized. tx=${tx}`);
  } catch (e: any) {
    console.log(`initialize skipped/already initialized: ${e}`);
  }

  const config = await program.account.presaleConfig.fetch(configPda);
  console.log(`status=${JSON.stringify(config.status)}, totalSold=${config.totalSold.toString()}`);
}

async function setGlobalUnlock(unlockPct: number): Promise<void> {
  const tx = await program.methods
    .setUnlock(unlockPct)
    .accounts({
      config: configPda,
      admin: ADMIN_WALLET.publicKey,
    })
    .rpc();
  console.log(`setUnlock(${unlockPct}) tx=${tx}`);
}

async function ensureVaultLiquidity(minAmount: bigint): Promise<void> {
  console.log("\n--- 2) ensure vault liquidity ---");
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

async function readAllocationSnapshot(allocationPda: PublicKey): Promise<AllocationSnapshot> {
  const allocation = await program.account.userAllocation.fetch(allocationPda);
  return {
    amountPurchased: BigInt(allocation.amountPurchased.toString()),
    amountClaimed: BigInt(allocation.amountClaimed.toString()),
    claimableAmount: BigInt(allocation.claimableAmount.toString()),
    amountVesting: BigInt(allocation.amountVesting.toString()),
    lastUnlockPct: Number(allocation.lastUnlockPct),
  };
}

async function creditAllocationForUser(user: PublicKey, expectedTgePct?: number): Promise<PublicKey> {
  console.log("\n--- 4) credit allocation ---");

  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), user.toBuffer()],
    program.programId
  );

  const configBefore = await program.account.presaleConfig.fetch(configPda);
  const totalSoldBefore = BigInt(configBefore.totalSold.toString());
  const tgePctNum = Number(configBefore.tgePercentage);
  const tgePct = BigInt(tgePctNum);
  if (expectedTgePct !== undefined) {
    assertEq(tgePctNum, expectedTgePct, `credit allocation expects config.tge_percentage=${expectedTgePct}`);
  }
  console.log(`[CONFIG] credit round uses tge_percentage=${tgePctNum}`);
  const expectedTge = (TOKEN_AMOUNT_RAW * tgePct) / 100n;
  const expectedVesting = TOKEN_AMOUNT_RAW - expectedTge;

  const existingAllocation = await program.account.userAllocation.fetchNullable(allocationPda);
  const before = existingAllocation
    ? {
        amountPurchased: BigInt(existingAllocation.amountPurchased.toString()),
        amountClaimed: BigInt(existingAllocation.amountClaimed.toString()),
        claimableAmount: BigInt(existingAllocation.claimableAmount.toString()),
        amountVesting: BigInt(existingAllocation.amountVesting.toString()),
      }
    : {
        amountPurchased: 0n,
        amountClaimed: 0n,
        claimableAmount: 0n,
        amountVesting: 0n,
      };

  // Convert user PublicKey to 32-byte identity_key
  const identityKey = user.toBuffer();
  
  const tx = await program.methods
    .creditAllocation(identityKey, new anchor.BN(TOKEN_AMOUNT_RAW.toString()), USD_AMOUNT, `payment_${Date.now()}`)
    .accounts({
      config: configPda,
      dailyState: dailyStatePda,
      userAllocation: allocationPda,
      admin: ADMIN_WALLET.publicKey,
      systemProgram: SystemProgram.programId,
    })
    .rpc();
  console.log(`creditAllocation tx=${tx}`);

  const after = await readAllocationSnapshot(allocationPda);
  const configAfter = await program.account.presaleConfig.fetch(configPda);
  const totalSoldAfter = BigInt(configAfter.totalSold.toString());

  assertEq(after.amountPurchased - before.amountPurchased, TOKEN_AMOUNT_RAW, "amountPurchased delta mismatch");
  assertEq(after.claimableAmount - before.claimableAmount, expectedTge, "claimable TGE delta mismatch");
  assertEq(after.amountVesting - before.amountVesting, expectedVesting, "vesting delta mismatch");
  assertEq(after.amountClaimed - before.amountClaimed, 0n, "amountClaimed changed unexpectedly during credit");
  assertEq(totalSoldAfter - totalSoldBefore, TOKEN_AMOUNT_RAW, "config.totalSold delta mismatch");

  console.log("credit allocation assertions passed");
  return allocationPda;
}

async function updateConfigTge(newTgePct: number): Promise<void> {
  console.log(`\n--- config update: set TGE=${newTgePct}% ---`);
  let config = await program.account.presaleConfig.fetch(configPda);
  const dailyState = await program.account.dailyState.fetch(dailyStatePda);
  const oldTge = Number(config.tgePercentage);
  console.log(`[CONFIG] before update tge_percentage=${oldTge}`);

  if (oldTge === newTgePct) {
    console.log("[CONFIG] target TGE already set, skipping updateConfig call");
    return;
  }

  const currentDailyCap = BigInt(config.dailyCap.toString());
  const soldTodayCfg = BigInt(config.soldToday.toString());
  const soldTodayDaily = BigInt(dailyState.soldToday.toString());
  const burnManual = currentDailyCap - soldTodayCfg;
  const burnRollover = currentDailyCap > soldTodayDaily ? currentDailyCap - soldTodayDaily : 0n;
  const expectedBurn = burnManual + burnRollover;
  const reserveForClaims = TOKEN_AMOUNT_RAW * 2n;
  const requiredBeforeUpdate = expectedBurn + reserveForClaims;

  const vaultBefore = await getAccount(provider.connection, vaultPda);
  if (vaultBefore.amount < requiredBeforeUpdate) {
    const topUp = requiredBeforeUpdate - vaultBefore.amount;
    const mintSig = await mintTo(
      provider.connection,
      ADMIN_WALLET.payer,
      TOKEN_MINT,
      vaultPda,
      ADMIN_WALLET.payer,
      topUp
    );
    console.log(`[CONFIG] pre-burn vault top-up=${topUp.toString()} tx=${mintSig}`);
  }

  const tx = await program.methods
    .updateConfig(config.tokenPriceUsd, newTgePct, config.dailyCap)
    .accounts({
      config: configPda,
      dailyState: dailyStatePda,
      admin: ADMIN_WALLET.publicKey,
      tokenMint: TOKEN_MINT,
      vaultTokenAccount: vaultPda,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();
  console.log(`[CONFIG] updateConfig tx=${tx}`);

  config = await program.account.presaleConfig.fetch(configPda);
  assertEq(Number(config.tgePercentage), newTgePct, `tge_percentage should be ${newTgePct} after config update`);
  console.log(`[CONFIG] after update tge_percentage=${Number(config.tgePercentage)}`);
}

async function setStatusTokenLaunched(): Promise<void> {
  console.log("\n--- 5) set status token launched ---");
  const tx = await program.methods
    .setStatus({ tokenLaunched: {} })
    .accounts({
      config: configPda,
      dailyState: dailyStatePda,
      admin: ADMIN_WALLET.publicKey,
      tokenMint: TOKEN_MINT,
      vaultTokenAccount: vaultPda,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();
  console.log(`setStatus(tokenLaunched) tx=${tx}`);
}

async function ensureUserAta(user: Keypair): Promise<PublicKey> {
  const ata = await getOrCreateAssociatedTokenAccount(
    provider.connection,
    user,
    TOKEN_MINT,
    user.publicKey
  );
  return ata.address;
}

async function claimAndAssert(user: Keypair, allocationPda: PublicKey, userAta: PublicKey, label: string): Promise<void> {
  const beforeAllocation = await readAllocationSnapshot(allocationPda);
  const beforeUserToken = await getAccount(provider.connection, userAta);
  const beforeVaultToken = await getAccount(provider.connection, vaultPda);
  const claimableBefore = beforeAllocation.claimableAmount;
  const configBefore = await program.account.presaleConfig.fetch(configPda);
  const globalUnlockPct = Number(configBefore.globalUnlockPct);
  const unlockDeltaPct = Math.max(globalUnlockPct - beforeAllocation.lastUnlockPct, 0);
  const newlyUnlocked = (beforeAllocation.amountVesting * BigInt(unlockDeltaPct)) / 100n;
  const expectedClaimDelta = claimableBefore + newlyUnlocked;
  logBalance(`${label} claim - user sale-token before`, beforeUserToken.amount);
  logBalance(`${label} claim - vault sale-token before`, beforeVaultToken.amount);
  console.log(`[CHECK] ${label} expected claim delta: ${expectedClaimDelta.toString()}`);

  const tx = await program.methods
    .claim()
    .accounts({
      config: configPda,
      userAllocation: allocationPda,
      user: user.publicKey,
      vaultTokenAccount: vaultPda,
      userTokenAccount: userAta,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .transaction();
  tx.feePayer = user.publicKey;

  const { blockhash } = await provider.connection.getLatestBlockhash();
  tx.recentBlockhash = blockhash;

  const txSig = await anchor.web3.sendAndConfirmTransaction(provider.connection, tx, [user]);
  console.log(`${label} claim tx=${txSig} (payer=test user)`);

  const afterAllocation = await readAllocationSnapshot(allocationPda);
  const afterUserToken = await getAccount(provider.connection, userAta);
  const afterVaultToken = await getAccount(provider.connection, vaultPda);
  logBalance(`${label} claim - user sale-token after`, afterUserToken.amount);
  logBalance(`${label} claim - vault sale-token after`, afterVaultToken.amount);

  assertEq(afterAllocation.claimableAmount, 0n, `${label} claimable should be zero after claim`);
  assertEq(
    afterAllocation.amountClaimed - beforeAllocation.amountClaimed,
    expectedClaimDelta,
    `${label} claimed delta mismatch`
  );
  assertEq(
    afterUserToken.amount - beforeUserToken.amount,
    expectedClaimDelta,
    `${label} user token balance delta mismatch`
  );

  console.log(`${label} claim assertions passed`);
}

async function runFullFlow(): Promise<void> {
  console.log("Starting decomposed presale full-flow tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);
  console.log(`Sale token mint: ${TOKEN_MINT.toBase58()}`);
  console.log(`Payment token mint: ${PAYMENT_MINT.toBase58()}`);

  await initializePresale();
  await setGlobalUnlock(0);
  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW);

  const testUser = Keypair.generate();
  console.log(`Test user: ${testUser.publicKey.toBase58()}`);

  await fundTestUserIfNeeded(testUser.publicKey, TEST_USER_SOL_TARGET);

  const configBeforeFirstCredit = await program.account.presaleConfig.fetch(configPda);
  const firstRoundTgePct = Number(configBeforeFirstCredit.tgePercentage);
  console.log(`[FLOW] first round TGE=${firstRoundTgePct}%`);

  await preparePaymentAndSimulatePurchase(testUser);

  const allocationPda = await creditAllocationForUser(testUser.publicKey, firstRoundTgePct);
  console.log(`Allocation PDA: ${allocationPda.toBase58()}`);

  await updateConfigTge(TARGET_TGE_PERCENTAGE);

  await preparePaymentAndSimulatePurchase(testUser);
  await creditAllocationForUser(testUser.publicKey, TARGET_TGE_PERCENTAGE);

  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW * 2n);

  const allocationAfterTwoRounds = await readAllocationSnapshot(allocationPda);
  const expectedTotalClaimable =
    (TOKEN_AMOUNT_RAW * BigInt(firstRoundTgePct)) / 100n +
    (TOKEN_AMOUNT_RAW * BigInt(TARGET_TGE_PERCENTAGE)) / 100n;
  const expectedTotalPurchased = TOKEN_AMOUNT_RAW * 2n;
  assertEq(
    allocationAfterTwoRounds.amountPurchased,
    expectedTotalPurchased,
    "after two rounds amountPurchased should equal 2 allocations"
  );
  assertEq(
    allocationAfterTwoRounds.claimableAmount,
    expectedTotalClaimable,
    "after two rounds claimableAmount should match both TGE rounds"
  );
  console.log(`[CHECK] after two rounds total claimable=${allocationAfterTwoRounds.claimableAmount.toString()}`);

  await setStatusTokenLaunched();

  const userAta = await ensureUserAta(testUser);
  console.log(`User ATA: ${userAta.toBase58()}`);
  await claimAndAssert(testUser, allocationPda, userAta, "TGE");

  await setGlobalUnlock(GLOBAL_UNLOCK_TARGET);
  await claimAndAssert(testUser, allocationPda, userAta, "Vesting unlock");

  const beforeNoop = await readAllocationSnapshot(allocationPda);
  await claimAndAssert(testUser, allocationPda, userAta, "No-op");
  const afterNoop = await readAllocationSnapshot(allocationPda);
  assertEq(afterNoop.amountClaimed - beforeNoop.amountClaimed, 0n, "No-op claim should not increase amountClaimed");

  console.log("\nAll full-flow assertions passed.");
}

runFullFlow().catch((err) => {
  console.error("Test failed:");
  console.error(err);
  process.exit(1);
});
