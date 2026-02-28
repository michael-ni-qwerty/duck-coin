// ANCHOR_PROVIDER_URL=https://api.devnet.solana.com ANCHOR_WALLET=/home/michael/.config/solana/id.json npx ts-node --project scripts/tsconfig.json scripts/tests/evm-flow.ts

import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey } from "@solana/web3.js";
import { getAccount } from "@solana/spl-token";
import {
  provider,
  program,
  ADMIN_WALLET,
  TOKEN_MINT,
  PAYMENT_MINT,
  configPda,
  vaultPda,
  assertEq,
  readAllocationSnapshot,
  ensureUserAta,
  fundTestUserIfNeeded,
  ensureVaultLiquidity,
  TOKEN_AMOUNT_RAW,
  TEST_USER_SOL_TARGET,
  GLOBAL_UNLOCK_TARGET,
  TARGET_TGE_PERCENTAGE
} from "./config";

import { initializePresale, setGlobalUnlock } from "./setup";
import { creditAllocationForUser } from "./allocation";
import { claimAndAssert, setStatusTokenLaunched, bindClaimWallet } from "./claiming";
import { updateConfigTge } from "./config-management";

async function runEvmFlow(): Promise<void> {
  console.log("Starting EVM address presale full-flow tests...");
  console.log(`Program ID: ${program.programId.toBase58()}`);
  console.log(`Admin: ${ADMIN_WALLET.publicKey.toBase58()}`);

  // 1. Setup and initialization
  await initializePresale();
  await setGlobalUnlock(0);
  await ensureVaultLiquidity(TOKEN_AMOUNT_RAW);

  // 2. Create test user (Solana wallet for claiming) and EVM identity
  const testUser = Keypair.generate();
  const evmAddress = "0x1234567890123456789012345678901234567890";
  // Convert 20-byte EVM address to 32-byte identity key (left-padded with zeros)
  const identityKey = Buffer.alloc(32);
  Buffer.from(evmAddress.slice(2), "hex").copy(identityKey, 12);

  console.log(`Test user (claim wallet): ${testUser.publicKey.toBase58()}`);
  console.log(`EVM Identity: ${evmAddress}`);
  console.log(`Identity Key (hex): ${identityKey.toString("hex")}`);

  await fundTestUserIfNeeded(testUser.publicKey, TEST_USER_SOL_TARGET);

  // 3. First allocation round (using EVM identity)
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

  // 9. Bind claim wallet
  // This step connects the EVM identity to the Solana testUser wallet
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

  // 13. Final state verification
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

  console.log("\nEVM flow assertions passed.");
}

runEvmFlow().catch((err) => {
  console.error("EVM flow test failed:");
  console.error(err);
  process.exit(1);
});
