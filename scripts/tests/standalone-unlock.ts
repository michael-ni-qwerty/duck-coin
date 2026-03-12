import { program, configPda, ADMIN_WALLET } from "../config";

export async function setGlobalUnlock(unlockPct: number): Promise<void> {
  const tx = await program.methods
    .setUnlock(unlockPct)
    .accounts({
      config: configPda,
      admin: ADMIN_WALLET.publicKey,
    })
    .rpc();
  console.log(`setUnlock(${unlockPct}) tx=${tx}`);
}

export async function unlockOnly(): Promise<void> {
  console.log("\n--- Set Global Unlock Standalone Test ---");

  // Read arguments for unlock percentage, default to 10 if none provided
  const args = process.argv.slice(2);
  const targetUnlock = args.length > 0 ? parseInt(args[0], 10) : 10;

  if (isNaN(targetUnlock) || targetUnlock < 0 || targetUnlock > 100) {
    console.error("Please provide a valid unlock percentage between 0 and 100");
    process.exit(1);
  }

  let config = await program.account.presaleConfig.fetch(configPda);
  console.log(`Current global unlock: ${config.globalUnlockPct}%`);

  if (targetUnlock < config.globalUnlockPct) {
    console.log(`Error: Target unlock (${targetUnlock}%) cannot be less than current unlock (${config.globalUnlockPct}%)`);
    process.exit(1);
  }

  console.log(`Setting global unlock to ${targetUnlock}%...`);
  await setGlobalUnlock(targetUnlock);

  config = await program.account.presaleConfig.fetch(configPda);
  console.log(`New global unlock: ${config.globalUnlockPct}%`);
}

if (require.main === module) {
  unlockOnly().catch((err) => {
    console.error("Unlock test failed:");
    console.error(err);
    process.exit(1);
  });
}
