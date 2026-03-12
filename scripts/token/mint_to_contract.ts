import {
  mintTo,
  setAuthority,
  AuthorityType,
} from "@solana/spl-token";
import { connection, payer, TOKEN_MINT, configPda, vaultPda } from "../config";

// Token Configuration
const DECIMALS = 6;
const TOTAL_SUPPLY_AMOUNT = 2_400_000_000; // 2.4 Billion tokens for presale
const RAW_AMOUNT = TOTAL_SUPPLY_AMOUNT * Math.pow(10, DECIMALS);

async function main() {
  console.log(`Payer address: ${payer.publicKey.toBase58()}`);
  console.log(`Mint address: ${TOKEN_MINT.toBase58()}`);

  console.log(`\nContract Config PDA: ${configPda.toBase58()}`);
  console.log(`Contract Vault PDA: ${vaultPda.toBase58()}`);

  // 2. Mint the supply directly to the contract's vault PDA
  console.log(`\nMinting ${TOTAL_SUPPLY_AMOUNT} tokens to the contract vault...`);
  try {
    const mintSig = await mintTo(
      connection,
      payer,
      TOKEN_MINT,
      vaultPda,
      payer,
      RAW_AMOUNT
    );
    console.log(`✅ Minted successfully. Signature: ${mintSig}`);
  } catch (error) {
    console.error("❌ Failed to mint tokens:", error);
    process.exit(1);
  }

  console.log("\n=======================================================");
  console.log("🎉 Token Minting to Contract Complete!");
  console.log("=======================================================");
}

main().catch((err) => {
  console.error("Execution failed:", err);
});
