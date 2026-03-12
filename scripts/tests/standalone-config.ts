import * as anchor from "@coral-xyz/anchor";
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
  TOKEN_AMOUNT_RAW,
} from "../config";

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
  const soldTodayDaily = BigInt(dailyState.soldToday.toString());
  const expectedBurn = currentDailyCap > soldTodayDaily ? currentDailyCap - soldTodayDaily : 0n;
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

export async function updateConfigOnly(): Promise<void> {
  console.log("\n--- Update Config Standalone Test ---");
  const args = process.argv.slice(2);
  const targetTge = args.length > 0 ? parseInt(args[0], 10) : 30;

  if (isNaN(targetTge) || targetTge < 0 || targetTge > 100) {
    console.error("Please provide a valid TGE percentage between 0 and 100");
    process.exit(1);
  }

  await updateConfigTge(targetTge);
}

if (require.main === module) {
  updateConfigOnly().catch((err) => {
    console.error("Config update test failed:");
    console.error(err);
    process.exit(1);
  });
}
