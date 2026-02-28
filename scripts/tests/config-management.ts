// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/tests/config-management.ts

import * as anchor from "@coral-xyz/anchor";
import { SYSVAR_RENT_PUBKEY } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAccount, mintTo } from "@solana/spl-token";
import {
  provider,
  program,
  ADMIN_WALLET,
  TOKEN_MINT,
  configPda,
  dailyStatePda,
  vaultPda,
  assertEq,
  logBalance,
  TOKEN_AMOUNT_RAW,
  TARGET_TGE_PERCENTAGE
} from "./config";

export async function updateConfigTge(newTgePct: number): Promise<void> {
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
    .updateConfig(config.tokenPriceUsd, newTgePct, config.dailyCap, config.startTime)
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

async function setStatusTokenLaunched(): Promise<void> {
  console.log("\n--- set status token launched ---");
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

async function readConfigState(): Promise<void> {
  console.log("\n--- reading config state ---");
  const config = await program.account.presaleConfig.fetch(configPda);
  const dailyState = await program.account.dailyState.fetch(dailyStatePda);

  console.log(`[CONFIG] status=${JSON.stringify(config.status)}`);
  console.log(`[CONFIG] tokenPriceUsd=${config.tokenPriceUsd.toString()}`);
  console.log(`[CONFIG] tgePercentage=${Number(config.tgePercentage)}%`);
  console.log(`[CONFIG] dailyCap=${config.dailyCap.toString()}`);
  console.log(`[CONFIG] totalSold=${config.totalSold.toString()}`);
  console.log(`[CONFIG] globalUnlockPct=${Number(config.globalUnlockPct)}%`);
  console.log(`[CONFIG] soldToday=${config.soldToday.toString()}`);
  console.log(`[DAILY_STATE] soldToday=${dailyState.soldToday.toString()}`);
  // Removed logging of dailyState.lastReset which caused issues with some IDL versions
}

async function changeStartTime(): Promise<void> {
  console.log("\n--- change start time to tomorrow ---");
  let config = await program.account.presaleConfig.fetch(configPda);
  const dailyState = await program.account.dailyState.fetch(dailyStatePda);
  const oldStartTime = Number(config.startTime);
  console.log(`[CONFIG] before update start_time=${oldStartTime} (${new Date(oldStartTime * 1000).toLocaleString()})`);

  const dayTomorrow = new anchor.BN(Math.floor(Date.now() / 1000) + 86400);
  console.log(`[CONFIG] setting start_time to tomorrow=${dayTomorrow.toString()} (${new Date(dayTomorrow.toNumber() * 1000).toLocaleString()})`);

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
    .updateConfig(config.tokenPriceUsd, config.tgePercentage, config.dailyCap, dayTomorrow)
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
  const newStartTime = Number(config.startTime);
  console.log(`[CONFIG] after update start_time=${newStartTime} (${new Date(newStartTime * 1000).toLocaleString()})`);
}

async function runConfigManagementTests(): Promise<void> {
  console.log("Starting config management tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);

  // await readConfigState();

  // await setGlobalUnlock(0);
  // await readConfigState();

  // await updateConfigTge(TARGET_TGE_PERCENTAGE);
  // await readConfigState();

  await changeStartTime();
  await readConfigState();

  // await setGlobalUnlock(15);
  // await readConfigState();

  // await setStatusTokenLaunched();
  // await readConfigState();

  console.log("\nConfig management tests completed successfully.");
}

if (require.main === module) {
  runConfigManagementTests().catch((err) => {
    console.error("Config management test failed:");
    console.error(err);
    process.exit(1);
  });
}
