import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey } from "@solana/web3.js";
import {
  program,
  ADMIN_WALLET,
  configPda,
  readAllocationSnapshot,
} from "../config";
import { creditAllocationForUser } from "./standalone-credit";

export async function bindClaimWallet(
  identityKey: Buffer | number[],
  claimAuthority: PublicKey,
  allocationPda: PublicKey,
): Promise<void> {
  console.log("\n--- bind claim wallet ---");
  console.log(`Identity key: ${Buffer.from(identityKey).toString("hex")}`);
  console.log(`Claim authority: ${claimAuthority.toBase58()}`);

  const tx = await program.methods
    .bindClaimWallet(Array.from(identityKey), claimAuthority)
    .accounts({
      config: configPda,
      userAllocation: allocationPda,
      admin: ADMIN_WALLET.publicKey,
    })
    .rpc();
  console.log(`bindClaimWallet tx=${tx}`);

  const allocation = await readAllocationSnapshot(allocationPda);
  console.log("bind claim wallet successful");
}

export async function bindOnly(): Promise<void> {
  console.log("\n--- Bind Claim Wallet Standalone Test ---");

  // Read arguments
  const args = process.argv.slice(2);
  let identityKeyStr = args[0];
  let claimAuthStr = args[1];

  let identityKey: Buffer;
  let claimAuthority: PublicKey;

  if (identityKeyStr && claimAuthStr) {
    identityKey = new PublicKey(identityKeyStr).toBuffer();
    claimAuthority = new PublicKey(claimAuthStr);
  } else {
    // Generate new if not provided
    console.log("No arguments provided. Generating a new test user to bind...");
    const testUser = Keypair.generate();
    console.log(`Test user generated: ${testUser.publicKey.toBase58()}`);
    identityKey = testUser.publicKey.toBuffer();
    claimAuthority = testUser.publicKey;

    console.log("Creating allocation to allow binding...");
    await creditAllocationForUser(identityKey, 50);
  }

  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), identityKey],
    program.programId,
  );

  console.log("Calling bind_claim_wallet...");
  await bindClaimWallet(identityKey, claimAuthority, allocationPda);

  // Fetch and verify it's bound
  const allocation = await program.account.userAllocation.fetch(allocationPda);
  console.log(`Bound authority: ${allocation.claimAuthority.toBase58()}`);
}

if (require.main === module) {
  bindOnly().catch((err) => {
    console.error("Bind test failed:");
    console.error(err);
    process.exit(1);
  });
}
