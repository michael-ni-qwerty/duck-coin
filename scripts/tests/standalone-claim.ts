import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAccount } from "@solana/spl-token";
import {
  provider,
  program,
  configPda,
  vaultPda,
  assertEq,
  logBalance,
  readAllocationSnapshot,
  ensureUserAta,
  fundTestUserIfNeeded,
  TEST_USER_SOL_TARGET
} from "../config";

export async function claimAndAssert(
  user: Keypair,
  allocationPda: PublicKey,
  userAta: PublicKey,
  label: string,
  identityKey: Buffer | number[]
): Promise<void> {
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
    .claim(Array.from(identityKey))
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

  try {
    const txSig = await anchor.web3.sendAndConfirmTransaction(provider.connection, tx, [user]);
    console.log(`${label} claim tx=${txSig} (payer=test user)`);

    if (expectedClaimDelta === 0n) {
      throw new Error(`${label} claim succeeded but expected NothingToClaim error`);
    }
  } catch (err: any) {
    if (expectedClaimDelta === 0n && err.logs && err.logs.some((log: string) => log.includes("NothingToClaim"))) {
      console.log(`${label} claim correctly failed with NothingToClaim as expected`);
      return;
    }
    throw err;
  }

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

export async function claimOnly(): Promise<void> {
  console.log("\n--- Claim Only Standalone Test ---");

  const args = process.argv.slice(2);
  let identityKeyStr = args[0];
  let claimAuthSecret = args[1];

  if (!identityKeyStr || !claimAuthSecret) {
    console.error("Usage: npx ts-node standalone-claim.ts <identity_pubkey> <claim_authority_secret_array>");
    console.error("Please provide an existing identity public key and its matching bound claim authority secret key.");
    process.exit(1);
  }

  const identityKey = new PublicKey(identityKeyStr).toBuffer();
  const secretKeyArr = JSON.parse(claimAuthSecret);
  const claimUser = Keypair.fromSecretKey(Uint8Array.from(secretKeyArr));

  console.log(`Identity Key: ${identityKeyStr}`);
  console.log(`Claim Authority User: ${claimUser.publicKey.toBase58()}`);

  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), identityKey],
    program.programId
  );

  let allocation;
  try {
    allocation = await readAllocationSnapshot(allocationPda);
  } catch (e) {
    console.error("No allocation found for this identity key. Please create an allocation first.");
    process.exit(1);
  }

  console.log(`Found allocation with ${allocation.claimableAmount.toString()} claimable tokens`);

  if (allocation.claimableAmount === 0n) {
    console.log("No claimable tokens currently available.");
    process.exit(0);
  }

  await fundTestUserIfNeeded(claimUser.publicKey, TEST_USER_SOL_TARGET);
  const userAta = await ensureUserAta(claimUser);

  console.log("Calling claim...");
  await claimAndAssert(claimUser, allocationPda, userAta, "Standalone Claim", identityKey);

  console.log("Claim successful.");
}

if (require.main === module) {
  claimOnly().catch((err) => {
    console.error("Claim test failed:");
    console.error(err);
    process.exit(1);
  });
}
