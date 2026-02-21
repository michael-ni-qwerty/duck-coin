import * as anchor from "@coral-xyz/anchor";
import { PublicKey, SystemProgram, Keypair, Connection } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, createInitializeAccountInstruction, getMinimumBalanceForRentExemptAccount, ACCOUNT_SIZE, createAssociatedTokenAccountInstruction, getAssociatedTokenAddress } from "@solana/spl-token";
import * as fs from "fs";

const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);

const TOKEN_MINT = new PublicKey("6YskGKuqzVX9rjxvWkvN3vUC5BH6rZ7faKgzzWjdmLca");
const ADMIN_WALLET = provider.wallet;
const programId = new PublicKey("J6uoJoaYaytU2PRedpzszvMZMmF4aNvAzHeqgtxQu1nN");

const [configPda] = PublicKey.findProgramAddressSync([Buffer.from("config")], programId);
const [vaultPda] = PublicKey.findProgramAddressSync([Buffer.from("vault"), configPda.toBuffer()], programId);

async function main() {
    console.log(`Config PDA: ${configPda.toBase58()}`);
    console.log(`Vault PDA: ${vaultPda.toBase58()}`);

    try {
        // Vault PDA is derived but SPL Token requires actual initialization or ATA
        // For PDA vault token account, we can't create it with system program and then init
        // because we don't have the keypair to sign the creation.
        // We must rely on an initialize instruction in the smart contract!
        
        console.log("We need to add token account initialization to the smart contract's initialize function.");
    } catch (err) {
        console.error("Vault init failed:");
        console.error(err);
    }
}

main();
