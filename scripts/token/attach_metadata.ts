import { createUmi } from "@metaplex-foundation/umi-bundle-defaults";
import {
  createMetadataAccountV3,
  updateMetadataAccountV2,
  fetchMetadataFromSeeds
} from "@metaplex-foundation/mpl-token-metadata";
import { keypairIdentity, publicKey } from "@metaplex-foundation/umi";
import { connection, payer, TOKEN_MINT } from "../config";
import * as fs from "fs";
import * as path from "path";
import bs58 from "bs58";

const URI = "https://moccasin-odd-egret-811.mypinata.cloud/ipfs/bafkreicwfafwdavviopfmcevzy5bb4rqbkizmcs5kxmqbolq7jsd5rymrq";

async function main() {
  console.log("Loading metadata configuration...");
  const metaPath = path.join(__dirname, "meta.json");
  const metaData = JSON.parse(fs.readFileSync(metaPath, "utf8"));

  console.log("Initializing Umi...");
  const umi = createUmi(connection.rpcEndpoint);

  // Convert solana web3.js keypair to Umi keypair
  const umiKeypair = umi.eddsa.createKeypairFromSecretKey(payer.secretKey);
  umi.use(keypairIdentity(umiKeypair));

  const mintPubkey = publicKey(TOKEN_MINT.toBase58());

  console.log(`\nAttaching metadata to token mint: ${TOKEN_MINT.toBase58()}`);
  console.log(`Payer/Authority: ${payer.publicKey.toBase58()}`);
  console.log(`Name: ${metaData.name}`);
  console.log(`Symbol: ${metaData.symbol}`);
  console.log(`URI: ${URI}\n`);

  try {
    let tx;
    try {
      // Check if metadata exists
      await fetchMetadataFromSeeds(umi, { mint: mintPubkey });
      console.log("Metadata already exists, updating...");
      tx = updateMetadataAccountV2(umi, {
        metadata: umi.eddsa.findPda(
          publicKey("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"),
          [
            Buffer.from("metadata"),
            bs58.decode("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"),
            bs58.decode(mintPubkey),
          ]
        ),
        updateAuthority: umi.identity,
        data: {
          name: metaData.name,
          symbol: metaData.symbol,
          uri: URI,
          sellerFeeBasisPoints: 0,
          creators: null,
          collection: null,
          uses: null,
        },
        primarySaleHappened: null,
        isMutable: true,
      });
    } catch (e) {
      console.log("Metadata does not exist, creating...");
      tx = createMetadataAccountV3(umi, {
        mint: mintPubkey,
        mintAuthority: umi.identity,
        payer: umi.identity,
        updateAuthority: umi.identity.publicKey,
        data: {
          name: metaData.name,
          symbol: metaData.symbol,
          uri: URI,
          sellerFeeBasisPoints: 0,
          creators: null,
          collection: null,
          uses: null,
        },
        isMutable: true,
        collectionDetails: null,
      });
    }

    console.log("Sending transaction...");
    const result = await tx.sendAndConfirm(umi);

    console.log("✅ Metadata attached successfully!");
    console.log("Transaction signature:", bs58.encode(result.signature));
  } catch (error) {
    console.error("❌ Failed to attach metadata:", error);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("Execution failed:", err);
});
