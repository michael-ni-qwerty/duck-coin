import * as anchor from "@coral-xyz/anchor";
import { PublicKey, Keypair } from "@solana/web3.js";
import { mintTo, getOrCreateAssociatedTokenAccount } from "@solana/spl-token";
import * as fs from "fs";

const provider = anchor.AnchorProvider.env();
anchor.setProvider(provider);

const TOKEN_MINT = new PublicKey("6YskGKuqzVX9rjxvWkvN3vUC5BH6rZ7faKgzzWjdmLca");
const ADMIN_WALLET = Keypair.fromSecretKey(
  new Uint8Array(JSON.parse(fs.readFileSync("/home/michael/.config/solana/id.json", "utf8")))
);

const programId = new PublicKey("66Qho8H4xsVLBqZNLyvxTwRrgMP319rt5EuN2ZzaFay8");
const [configPda] = PublicKey.findProgramAddressSync([Buffer.from("config")], programId);
const [vaultPda] = PublicKey.findProgramAddressSync([Buffer.from("vault_v2"), configPda.toBuffer()], programId);

async function main() {
    console.log(`Vault PDA: ${vaultPda.toBase58()}`);

    try {
        const amount = 2_400_000_000n * 1_000_000_000n; // 2.4 Billion tokens
        
        console.log(`Minting ${amount.toString()} tokens to vault...`);
        const sig = await mintTo(
            provider.connection,
            ADMIN_WALLET,
            TOKEN_MINT,
            vaultPda,
            ADMIN_WALLET,
            amount
        );
        
        console.log(`Minted successfully! TX: ${sig}`);
    } catch (err) {
        console.error("Minting failed:");
        console.error(err);
    }
}

main();
