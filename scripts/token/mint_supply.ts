import {
  getOrCreateAssociatedTokenAccount,
  mintTo,
} from "@solana/spl-token";
import { connection, payer, TOKEN_MINT } from "../config";

// Token Configuration
const DECIMALS = 6;
const TOTAL_SUPPLY_AMOUNT = 10_000_000_000; // Total supply of 10B tokens
const RAW_AMOUNT = TOTAL_SUPPLY_AMOUNT * Math.pow(10, DECIMALS);

async function main() {
  console.log(`Payer address: ${payer.publicKey.toBase58()}`);
  console.log(`Mint address: ${TOKEN_MINT.toBase58()}`);

  // 1. Get or create the Associated Token Account (ATA) for the payer
  console.log("\nGetting/Creating ATA for the payer...");
  const tokenAccount = await getOrCreateAssociatedTokenAccount(
    connection,
    payer,
    TOKEN_MINT,
    payer.publicKey
  );
  console.log(`✅ ATA ready: ${tokenAccount.address.toBase58()}`);

  // 2. Mint the supply to the ATA
  console.log(`\nMinting ${TOTAL_SUPPLY_AMOUNT} tokens...`);
  const mintSig = await mintTo(
    connection,
    payer,
    TOKEN_MINT,
    tokenAccount.address,
    payer,
    RAW_AMOUNT
  );
  console.log(`✅ Minted successfully. Signature: ${mintSig}`);

  console.log("\n=======================================================");
  console.log("🎉 Token Minting Complete! Authority was NOT revoked.");
  console.log("=======================================================");
}

main().catch((err) => {
  console.error("Execution failed:", err);
});
