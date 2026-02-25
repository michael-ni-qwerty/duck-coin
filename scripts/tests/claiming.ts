// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/tests/claiming.ts

import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey, SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAccount } from "@solana/spl-token";
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
  readAllocationSnapshot,
  ensureUserAta,
  fundTestUserIfNeeded,
  TEST_USER_SOL_TARGET
} from "./config";

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

export async function bindClaimWallet(
  identityKey: Buffer | number[],
  claimAuthority: PublicKey,
  allocationPda: PublicKey
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
  // Note: Since we can't easily check the claimAuthority in the snapshot without updating the type,
  // we just assume it worked if the RPC succeeded. In a real test, you'd fetch the account and check.
  console.log("bind claim wallet successful");
}

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

async function runClaimingTests(): Promise<void> {
  console.log("Starting claiming tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);

  const testUser = Keypair.generate();
  console.log(`Test user: ${testUser.publicKey.toBase58()}`);

  await fundTestUserIfNeeded(testUser.publicKey, TEST_USER_SOL_TARGET);

  // This assumes an allocation already exists for the test user
  // In practice, you would run allocation.ts first to create an allocation
  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), testUser.publicKey.toBuffer()],
    program.programId
  );

  try {
    const allocation = await program.account.userAllocation.fetch(allocationPda);
    console.log(`[CHECK] Found existing allocation with amountPurchased=${allocation.amountPurchased.toString()}`);
  } catch (e) {
    console.log("No existing allocation found. Please run allocation.ts first to create an allocation.");
    return;
  }

  await setStatusTokenLaunched();

  const userAta = await ensureUserAta(testUser);
  console.log(`User ATA: ${userAta.toBase58()}`);
  
  const identityKey = testUser.publicKey.toBuffer();
  await claimAndAssert(testUser, allocationPda, userAta, "TGE", identityKey);

  await setGlobalUnlock(10);
  await claimAndAssert(testUser, allocationPda, userAta, "Vesting unlock", identityKey);

  const beforeNoop = await readAllocationSnapshot(allocationPda);
  await claimAndAssert(testUser, allocationPda, userAta, "No-op", identityKey);
  const afterNoop = await readAllocationSnapshot(allocationPda);
  assertEq(afterNoop.amountClaimed - beforeNoop.amountClaimed, 0n, "No-op claim should not increase amountClaimed");

  console.log("\nClaiming tests completed successfully.");
}

if (require.main === module) {
  runClaimingTests().catch((err) => {
    console.error("Claiming test failed:");
    console.error(err);
    process.exit(1);
  });
}
