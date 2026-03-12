import * as anchor from "@coral-xyz/anchor";
import { SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID } from "@solana/spl-token";
import {
  program,
  ADMIN_WALLET,
  configPda,
  dailyStatePda,
  vaultPda,
  TOKEN_MINT,
} from "../config";

export async function initialize(startTimeOverride?: number): Promise<void> {
  console.log("\n--- Initialize Presale ---");
  // Default to 1 day from now if not provided
  const startTime = new anchor.BN(startTimeOverride || Math.floor(Date.now() / 1000) + 86400);

  const existingConfig = await program.account.presaleConfig.fetchNullable(configPda);
  if (existingConfig) {
    console.log("Presale already initialized!");
    return;
  }

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
  console.log(`Initialized successfully. tx=${tx}`);

  const config = await program.account.presaleConfig.fetch(configPda);
  console.log(`status=${JSON.stringify(config.status)}, start_time=${config.startTime.toString()}`);
}

if (require.main === module) {
  // Try to parse CLI argument for timestamp
  const arg = process.argv[2];
  const startTime = arg ? parseInt(arg, 10) : undefined;

  initialize(startTime).catch((err) => {
    console.error("Initialize failed:");
    console.error(err);
    process.exit(1);
  });
}
