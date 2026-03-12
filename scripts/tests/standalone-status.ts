import { program, configPda, dailyStatePda, ADMIN_WALLET, TOKEN_MINT, vaultPda } from "../config";
import { TOKEN_PROGRAM_ID } from "@solana/spl-token";

export async function setStatusTokenLaunched(): Promise<void> {
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

export async function setStatusPresaleActive(): Promise<void> {
  console.log("\n--- set status presale active ---");
  const tx = await program.methods
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
  console.log(`setStatus(presaleActive) tx=${tx}`);
}

export async function setStatusPresaleEnded(): Promise<void> {
  console.log("\n--- set status presale ended ---");
  const tx = await program.methods
    .setStatus({ presaleEnded: {} })
    .accounts({
      config: configPda,
      dailyState: dailyStatePda,
      admin: ADMIN_WALLET.publicKey,
      tokenMint: TOKEN_MINT,
      vaultTokenAccount: vaultPda,
      tokenProgram: TOKEN_PROGRAM_ID,
    })
    .rpc();
  console.log(`setStatus(presaleEnded) tx=${tx}`);
}

export async function statusOnly(): Promise<void> {
  console.log("\n--- Set Status Standalone Test ---");

  let config = await program.account.presaleConfig.fetch(configPda);
  console.log(`Current status: ${JSON.stringify(config.status)}`);

  const args = process.argv.slice(2);
  const targetStatus = args[0] || "tokenLaunched";

  if (targetStatus === "presaleActive") {
    await setStatusPresaleActive();
  } else if (targetStatus === "presaleEnded") {
    await setStatusPresaleEnded();
  } else {
    await setStatusTokenLaunched();
  }

  config = await program.account.presaleConfig.fetch(configPda);
  console.log(`New status: ${JSON.stringify(config.status)}`);
}

if (require.main === module) {
  statusOnly().catch((err) => {
    console.error("Status test failed:");
    console.error(err);
    process.exit(1);
  });
}
