import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { PublicKey, SystemProgram, Keypair, SYSVAR_RENT_PUBKEY } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID } from "@solana/spl-token";
import * as fs from "fs";

// Setup provider
const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);

// Read the IDL to get the program interface
const idl = JSON.parse(fs.readFileSync("/home/michael/Desktop/my/duck-coin/smart_contracts/target/idl/presale.json", "utf8"));
const programId = new PublicKey("J6uoJoaYaytU2PRedpzszvMZMmF4aNvAzHeqgtxQu1nN");
const program = new Program(idl, provider) as any;

const TOKEN_MINT = new PublicKey("6YskGKuqzVX9rjxvWkvN3vUC5BH6rZ7faKgzzWjdmLca");
const ADMIN_WALLET = provider.wallet;

// Derive PDAs
const [configPda] = PublicKey.findProgramAddressSync([Buffer.from("config_v2")], program.programId);
const [dailyStatePda] = PublicKey.findProgramAddressSync([Buffer.from("daily_state_v2")], program.programId);
const [vaultPda] = PublicKey.findProgramAddressSync([Buffer.from("vault_v2"), configPda.toBuffer()], program.programId);

async function main() {
    console.log("Starting presale tests...");
    console.log(`Program ID: ${program.programId.toBase58()}`);
    console.log(`Admin Wallet: ${ADMIN_WALLET.publicKey.toBase58()}`);
    console.log(`Token Mint: ${TOKEN_MINT.toBase58()}`);

    try {
        // 1. Initialize Presale
        console.log("\n--- 1. Initializing Presale ---");
        const startTime = new anchor.BN(Math.floor(Date.now() / 1000) - 3600); // Start 1 hour ago
        
        try {
            const tx = await program.methods.initialize(startTime)
                .accounts({
                    config: configPda,
                    dailyState: dailyStatePda,
                    admin: ADMIN_WALLET.publicKey,
                    tokenMint: TOKEN_MINT,
                    vaultTokenAccount: vaultPda,
                    systemProgram: SystemProgram.programId,
                    tokenProgram: TOKEN_PROGRAM_ID,
                    rent: SYSVAR_RENT_PUBKEY,
                })
                .rpc();
            console.log(`Presale initialized successfully. TX: ${tx}`);
        } catch (e: any) {
            console.log(`Initialization skipped or failed: ${e.message}`);
        }

        // 2. Fetch config
        let config = await program.account.presaleConfig.fetch(configPda);
        console.log(`Config total sold: ${config.totalSold.toString()}`);
        console.log(`Config daily cap: ${config.dailyCap.toString()}`);

        // 3. Test Credit Allocation
        console.log("\n--- 2. Testing Credit Allocation ---");
        const testUser = Keypair.generate();
        console.log(`Generated Test User: ${testUser.publicKey.toBase58()}`);
        
        const [allocationPda] = PublicKey.findProgramAddressSync(
            [Buffer.from("allocation_v2"), testUser.publicKey.toBuffer()], 
            program.programId
        );

        const tokenAmount = new anchor.BN(1000 * 10**9); // 1000 tokens
        const usdAmount = new anchor.BN(50 * 10**6); // $50.00
        const paymentId = "test_payment_123";

        const tx2 = await program.methods.creditAllocation(
            testUser.publicKey,
            tokenAmount,
            usdAmount,
            paymentId
        )
        .accounts({
            config: configPda,
            dailyState: dailyStatePda,
            userAllocation: allocationPda,
            admin: ADMIN_WALLET.publicKey,
            systemProgram: SystemProgram.programId,
        })
        .rpc();
        
        console.log(`Credit allocated successfully. TX: ${tx2}`);

        const allocation = await program.account.userAllocation.fetch(allocationPda);
        console.log(`User purchased: ${allocation.amountPurchased.toString()}`);
        console.log(`User claimable (TGE): ${allocation.claimableAmount.toString()}`);
        console.log(`User vesting: ${allocation.amountVesting.toString()}`);

        // 4. Test Update Config & Burn
        console.log("\n--- 3. Testing Update Config (Burn Logic) ---");
        const newPrice = new anchor.BN("60000000"); // 6 cents
        const newTge = 40; // 40%
        const newDailyCap = new anchor.BN("20000000000000000"); // Reduce to 20M tokens

        const tx3 = await program.methods.updateConfig(
            newPrice,
            newTge,
            newDailyCap
        )
        .accounts({
            config: configPda,
            dailyState: dailyStatePda,
            admin: ADMIN_WALLET.publicKey,
            tokenMint: TOKEN_MINT,
            vaultTokenAccount: vaultPda,
            tokenProgram: TOKEN_PROGRAM_ID,
        })
        .rpc();

        console.log(`Config updated successfully. TX: ${tx3}`);
        
        config = await program.account.presaleConfig.fetch(configPda);
        console.log(`Total Burned updated: ${config.totalBurned.toString()}`);

    } catch (err) {
        console.error("Test failed:");
        console.error(err);
    }
}

main();
