// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/tests/setup.ts

import * as anchor from "@coral-xyz/anchor";
import { Keypair, SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID } from "@solana/spl-token";
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
  ensureVaultLiquidity,
  TOKEN_AMOUNT_RAW
} from "./config";

export async function initializePresale(): Promise<void> {
  console.log("\n--- 1) initialize presale ---");
  const startTime = new anchor.BN(Math.floor(Date.now() / 1000) + 86400);

  const existingConfig = await program.account.presaleConfig.fetchNullable(configPda);
  if (existingConfig) {
    console.log("Presale already initialized. Updating status to PresaleActive if needed.");
    if (!existingConfig.status.presaleActive) {
      await program.methods
        .setStatus({ presaleActive: {} })
        .accounts({
          config: configPda,
          dailyState: dailyStatePda,
          admin: ADMIN_WALLET.publicKey,
          tokenMint: TOKEN_MINT,
          vaultTokenAccount: vaultPda,
          tokenProgram: TOKEN_PROGRAM_ID,
        })
        .rpc();
    }
  } else {
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
  }

  const config = await program.account.presaleConfig.fetch(configPda);
  console.log(`status=${JSON.stringify(config.status)}, totalSold=${config.totalSold.toString()}`);
}

export async function setGlobalUnlock(unlockPct: number): Promise<void> {
  const tx = await program.methods
    .setUnlock(unlockPct)
    .accounts({
      config: configPda,
      admin: ADMIN_WALLET.publicKey,
    })
    .rpc();
  console.log(`setUnlock(${unlockPct}) tx=${tx}`);
}

async function runSetupTests(): Promise<void> {
  console.log("Starting setup and initialization tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);
  console.log(`Sale token mint: ${TOKEN_MINT.toBase58()}`);

  await initializePresale();
  await setGlobalUnlock(0);
  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW);

  console.log("\nSetup tests completed successfully.");
}

if (require.main === module) {
  runSetupTests().catch((err) => {
    console.error("Setup test failed:");
    console.error(err);
    process.exit(1);
  });
}
