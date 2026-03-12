import { connection, PROGRAM_ID, vaultPda, configPda } from "../config";
import { getAccount } from "@solana/spl-token";

async function checkBalance() {
  console.log(`\nContract Config PDA: ${configPda.toBase58()}`);
  console.log(`Contract Vault PDA: ${vaultPda.toBase58()}`);

  console.log("\nChecking balance...");
  try {
    const vaultAccount = await getAccount(connection, vaultPda);
    // Presale Token decimals is 6
    const balance = Number(vaultAccount.amount) / Math.pow(10, 6);
    console.log(`\n=======================================================`);
    console.log(`💰 Vault Balance: ${balance.toLocaleString()} Tokens`);
    console.log(`=======================================================\n`);
  } catch (error) {
    console.error("❌ Failed to fetch balance. Ensure the contract is initialized and tokens are minted.");
    console.error(error);
  }
}

checkBalance().catch((err) => {
  console.error("Execution failed:", err);
});
