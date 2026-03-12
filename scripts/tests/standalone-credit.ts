import * as anchor from "@coral-xyz/anchor";
import { Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import {
  program,
  ADMIN_WALLET,
  configPda,
  dailyStatePda,
  assertEq,
  readAllocationSnapshot,
  TOKEN_AMOUNT_RAW,
  USD_AMOUNT
} from "../config";

export async function creditAllocationForUser(
  identityKey: Buffer | number[],
  expectedTgePct?: number
): Promise<PublicKey> {
  console.log("\n--- credit allocation ---");

  const [allocationPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("allocation"), Buffer.from(identityKey)],
    program.programId
  );

  const configBefore = await program.account.presaleConfig.fetch(configPda);
  const totalSoldBefore = BigInt(configBefore.totalSold.toString());
  const tgePctNum = Number(configBefore.tgePercentage);
  const tgePct = BigInt(tgePctNum);
  if (expectedTgePct !== undefined) {
    assertEq(tgePctNum, expectedTgePct, `credit allocation expects config.tge_percentage=${expectedTgePct}`);
  }
  console.log(`[CONFIG] credit round uses tge_percentage=${tgePctNum}`);
  const expectedTge = (TOKEN_AMOUNT_RAW * tgePct) / 100n;
  const expectedVesting = TOKEN_AMOUNT_RAW - expectedTge;

  const existingAllocation = await program.account.userAllocation.fetchNullable(allocationPda);
  const before = existingAllocation
    ? {
        amountPurchased: BigInt(existingAllocation.amountPurchased.toString()),
        amountClaimed: BigInt(existingAllocation.amountClaimed.toString()),
        claimableAmount: BigInt(existingAllocation.claimableAmount.toString()),
        amountVesting: BigInt(existingAllocation.amountVesting.toString()),
      }
    : {
        amountPurchased: 0n,
        amountClaimed: 0n,
        claimableAmount: 0n,
        amountVesting: 0n,
      };

  const tx = await program.methods
    .creditAllocation(
      Array.from(identityKey),
      new anchor.BN(TOKEN_AMOUNT_RAW.toString()),
      USD_AMOUNT,
      `payment_${Date.now()}`
    )
    .accounts({
      config: configPda,
      dailyState: dailyStatePda,
      userAllocation: allocationPda,
      admin: ADMIN_WALLET.publicKey,
      systemProgram: SystemProgram.programId,
    })
    .rpc();
  console.log(`creditAllocation tx=${tx}`);

  const after = await readAllocationSnapshot(allocationPda);
  const configAfter = await program.account.presaleConfig.fetch(configPda);
  const totalSoldAfter = BigInt(configAfter.totalSold.toString());

  assertEq(after.amountPurchased - before.amountPurchased, TOKEN_AMOUNT_RAW, "amountPurchased delta mismatch");
  assertEq(after.claimableAmount - before.claimableAmount, expectedTge, "claimable TGE delta mismatch");
  assertEq(after.amountVesting - before.amountVesting, expectedVesting, "vesting delta mismatch");
  assertEq(after.amountClaimed - before.amountClaimed, 0n, "amountClaimed changed unexpectedly during credit");
  assertEq(totalSoldAfter - totalSoldBefore, TOKEN_AMOUNT_RAW, "config.totalSold delta mismatch");

  console.log("credit allocation assertions passed");
  return allocationPda;
}

export async function creditOnly(): Promise<void> {
  console.log("\n--- Credit Allocation Standalone Test ---");
  const args = process.argv.slice(2);
  let identityKeyStr = args[0];

  let identityKey: Buffer;
  if (identityKeyStr) {
    identityKey = new PublicKey(identityKeyStr).toBuffer();
    console.log(`Using provided identity key: ${identityKeyStr}`);
  } else {
    const testUser = Keypair.generate();
    console.log(`Test user generated: ${testUser.publicKey.toBase58()}`);
    identityKey = testUser.publicKey.toBuffer();
  }

  const configBeforeFirstCredit = await program.account.presaleConfig.fetch(configPda);
  const firstRoundTgePct = Number(configBeforeFirstCredit.tgePercentage);
  console.log(`[FLOW] first round TGE=${firstRoundTgePct}%`);

  const allocationPda = await creditAllocationForUser(identityKey, firstRoundTgePct);
  console.log(`Allocation PDA: ${allocationPda.toBase58()}`);

  const allocation = await readAllocationSnapshot(allocationPda);
  console.log(`[CHECK] allocation amountPurchased=${allocation.amountPurchased.toString()}`);
  console.log(`[CHECK] allocation claimableAmount=${allocation.claimableAmount.toString()}`);
  console.log(`[CHECK] allocation amountVesting=${allocation.amountVesting.toString()}`);
}

if (require.main === module) {
  creditOnly().catch((err) => {
    console.error("Credit test failed:");
    console.error(err);
    process.exit(1);
  });
}
