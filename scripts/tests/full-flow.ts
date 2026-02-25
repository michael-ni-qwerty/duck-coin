// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/tests/full-flow.ts

import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey, SYSVAR_RENT_PUBKEY, SystemProgram } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAccount } from "@solana/spl-token";
import { 
  provider,
  program, 
  ADMIN_WALLET, 
  TOKEN_MINT, 
  PAYMENT_MINT,
  configPda, 
  dailyStatePda,
  vaultPda,
  assertEq,
  logBalance,
  readAllocationSnapshot,
  ensureUserAta,
  fundTestUserIfNeeded,
  ensureVaultLiquidity,
  TOKEN_AMOUNT_RAW,
  TEST_USER_SOL_TARGET,
  USD_AMOUNT,
  GLOBAL_UNLOCK_TARGET,
  TARGET_TGE_PERCENTAGE
} from "./config";

// Import functions from other test modules
import { initializePresale, setGlobalUnlock } from "./setup";
import { creditAllocationForUser } from "./allocation";
import { claimAndAssert, setStatusTokenLaunched } from "./claiming";
import { updateConfigTge } from "./config-management";

async function runFullFlow(): Promise<void> {
  console.log("Starting decomposed presale full-flow tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);
  console.log(`Sale token mint: ${TOKEN_MINT.toBase58()}`);
  console.log(`Payment token mint: ${PAYMENT_MINT.toBase58()}`);

  // 1. Setup and initialization
  await initializePresale();
  await setGlobalUnlock(0);
  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW);

  // 2. Create test user
  const testUser = Keypair.generate();
  console.log(`Test user: ${testUser.publicKey.toBase58()}`);
  const identityKey = testUser.publicKey.toBuffer();
  await fundTestUserIfNeeded(testUser.publicKey, TEST_USER_SOL_TARGET);

  // 3. First allocation round
  const configBeforeFirstCredit = await program.account.presaleConfig.fetch(configPda);
  const firstRoundTgePct = Number(configBeforeFirstCredit.tgePercentage);
  console.log(`[FLOW] first round TGE=${firstRoundTgePct}%`);

  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), identityKey],
    program.programId
  );
  await creditAllocationForUser(identityKey, firstRoundTgePct);
  console.log(`Allocation PDA: ${allocationPda.toBase58()}`);

  // 4. Update config for second round
  await updateConfigTge(TARGET_TGE_PERCENTAGE);

  // 5. Second allocation round
  await creditAllocationForUser(identityKey, TARGET_TGE_PERCENTAGE);

  // 6. Ensure vault has enough liquidity for claims
  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW * 2n);

  // 7. Verify allocation state after two rounds
  const allocationAfterTwoRounds = await readAllocationSnapshot(allocationPda);
  const expectedTotalClaimable =
    (TOKEN_AMOUNT_RAW * BigInt(firstRoundTgePct)) / 100n +
    (TOKEN_AMOUNT_RAW * BigInt(TARGET_TGE_PERCENTAGE)) / 100n;
  const expectedTotalPurchased = TOKEN_AMOUNT_RAW * 2n;
  
  assertEq(
    allocationAfterTwoRounds.amountPurchased,
    expectedTotalPurchased,
    "after two rounds amountPurchased should equal 2 allocations"
  );
  assertEq(
    allocationAfterTwoRounds.claimableAmount,
    expectedTotalClaimable,
    "after two rounds claimableAmount should match both TGE rounds"
  );
  console.log(`[CHECK] after two rounds total claimable=${allocationAfterTwoRounds.claimableAmount.toString()}`);

  // 8. Launch token and enable claiming
  await setStatusTokenLaunched();

  // 9. Bind claim wallet (Solana flow: binding same wallet is allowed if not already bound or same)
  // In the original flow, we didn't have bind_claim_wallet, but since the program now requires it:
  const { bindClaimWallet } = require("./claiming");
  await bindClaimWallet(identityKey, testUser.publicKey, allocationPda);

  // 10. TGE claim
  const userAta = await ensureUserAta(testUser);
  console.log(`User ATA: ${userAta.toBase58()}`);
  await claimAndAssert(testUser, allocationPda, userAta, "TGE", identityKey);

  // 11. Vesting unlock claim
  await setGlobalUnlock(GLOBAL_UNLOCK_TARGET);
  await claimAndAssert(testUser, allocationPda, userAta, "Vesting unlock", identityKey);

  // 12. No-op claim test
  const beforeNoop = await readAllocationSnapshot(allocationPda);
  await claimAndAssert(testUser, allocationPda, userAta, "No-op", identityKey);
  const afterNoop = await readAllocationSnapshot(allocationPda);
  assertEq(afterNoop.amountClaimed - beforeNoop.amountClaimed, 0n, "No-op claim should not increase amountClaimed");

  // 12. Final state verification
  const finalAllocation = await readAllocationSnapshot(allocationPda);
  const finalVault = await getAccount(provider.connection, vaultPda);
  const finalUserToken = await getAccount(provider.connection, userAta);
  
  console.log("\n=== FINAL STATE ===");
  console.log(`[FINAL] User total purchased: ${finalAllocation.amountPurchased.toString()}`);
  console.log(`[FINAL] User total claimed: ${finalAllocation.amountClaimed.toString()}`);
  console.log(`[FINAL] User claimable: ${finalAllocation.claimableAmount.toString()}`);
  console.log(`[FINAL] User vesting: ${finalAllocation.amountVesting.toString()}`);
  console.log(`[FINAL] User token balance: ${finalUserToken.amount.toString()}`);
  console.log(`[FINAL] Vault token balance: ${finalVault.amount.toString()}`);

  console.log("\nAll full-flow assertions passed.");
}

runFullFlow().catch((err) => {
  console.error("Full-flow test failed:");
  console.error(err);
  process.exit(1);
});
