# Solana Token Presale Smart Contract

A production-ready Solana smart contract for token presales with multi-currency payments, vesting, and off-chain authorization via ed25519 signatures.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESALE PROGRAM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Config    │    │   Vesting   │    │    Nonce    │    │    Vault    │  │
│  │    PDA      │    │   Account   │    │   Account   │    │    PDA      │  │
│  │             │    │    PDA      │    │    PDA      │    │             │  │
│  │ - treasury  │    │ - buyer     │    │ - is_used   │    │ - Holds     │  │
│  │ - signer    │    │ - purchased │    │ - nonce     │    │   presale   │  │
│  │ - pricing   │    │ - claimed   │    │ - timestamp │    │   tokens    │  │
│  │ - vesting   │    │             │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                              INSTRUCTIONS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   initialize    │  │  buy_tokens_spl │  │  buy_tokens_sol │              │
│  │                 │  │                 │  │                 │              │
│  │ Setup config,   │  │ Purchase with   │  │ Purchase with   │              │
│  │ vault, params   │  │ USDT/USDC       │  │ native SOL      │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  claim_tokens   │  │ deposit_tokens  │  │ withdraw_tokens │              │
│  │                 │  │                 │  │                 │              │
│  │ Claim vested    │  │ Admin deposits  │  │ Admin withdraws │              │
│  │ tokens          │  │ to vault        │  │ from vault      │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## PDA Seeds

| Account | Seeds | Description |
|---------|-------|-------------|
| Config | `["config"]` | Global configuration singleton |
| Vesting | `["vesting", buyer_pubkey]` | Per-user vesting tracker |
| Nonce | `["nonce", buyer_pubkey, nonce_bytes]` | Single-use nonce for replay protection |
| Vault | `["vault", config_pubkey]` | Token vault holding presale tokens |

## Transaction Flow

### Purchase Flow (SPL Token)

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Buyer   │────▶│ Off-chain    │────▶│  Build TX    │────▶│   Submit     │
│          │     │ Signer       │     │              │     │   to Chain   │
└──────────┘     └──────────────┘     └──────────────┘     └──────────────┘
     │                  │                    │                     │
     │ 1. Request       │                    │                     │
     │    signature     │                    │                     │
     │─────────────────▶│                    │                     │
     │                  │                    │                     │
     │ 2. Sign message  │                    │                     │
     │    with ed25519  │                    │                     │
     │◀─────────────────│                    │                     │
     │                  │                    │                     │
     │ 3. Build transaction with:           │                     │
     │    - ed25519 verify instruction      │                     │
     │    - buy_tokens_spl instruction      │                     │
     │───────────────────────────────────────▶                    │
     │                                                             │
     │ 4. Submit transaction                                       │
     │─────────────────────────────────────────────────────────────▶
     │                                                             │
     │                    ┌────────────────────────────────────────┤
     │                    │ 5. Verify ed25519 signature            │
     │                    │ 6. Verify nonce not used               │
     │                    │ 7. Transfer payment to treasury        │
     │                    │ 8. Update vesting account              │
     │                    └────────────────────────────────────────┤
     │                                                             │
     │ 9. Confirmation                                             │
     │◀────────────────────────────────────────────────────────────│
```

### Claim Flow

```
┌──────────┐                              ┌──────────────┐
│  Buyer   │─────────────────────────────▶│   Program    │
└──────────┘                              └──────────────┘
     │                                           │
     │ 1. Call claim_tokens                      │
     │──────────────────────────────────────────▶│
     │                                           │
     │                    ┌──────────────────────┤
     │                    │ 2. Calculate vested  │
     │                    │    amount based on   │
     │                    │    current time      │
     │                    │                      │
     │                    │ 3. Calculate         │
     │                    │    claimable =       │
     │                    │    vested - claimed  │
     │                    │                      │
     │                    │ 4. Transfer tokens   │
     │                    │    from vault        │
     │                    │                      │
     │                    │ 5. Update claimed    │
     │                    │    amount            │
     │                    └──────────────────────┤
     │                                           │
     │ 6. Tokens received                        │
     │◀──────────────────────────────────────────│
```

## Off-Chain Signature Construction

### Message Format

The off-chain signer must construct and sign a message with the following exact format:

```
┌────────────────────────────────────────────────────────────────┐
│ Offset │ Size  │ Field           │ Description                 │
├────────┼───────┼─────────────────┼─────────────────────────────┤
│ 0      │ 10    │ DOMAIN_SEPARATOR│ "PRESALE_V1" (ASCII bytes)  │
│ 10     │ 32    │ program_id      │ Presale program ID          │
│ 42     │ 32    │ buyer           │ Buyer's wallet pubkey       │
│ 74     │ 32    │ payment_mint    │ Payment token mint          │
│        │       │                 │ (Pubkey::default for SOL)   │
│ 106    │ 1     │ payment_type    │ 0=SOL, 1=USDT, 2=USDC       │
│ 107    │ 8     │ payment_amount  │ Little-endian u64           │
│ 115    │ 8     │ token_amount    │ Little-endian u64           │
│ 123    │ 8     │ nonce           │ Little-endian u64           │
└────────┴───────┴─────────────────┴─────────────────────────────┘
Total: 131 bytes
```

### TypeScript Example

```typescript
import { Keypair, PublicKey } from '@solana/web3.js';
import nacl from 'tweetnacl';

const DOMAIN_SEPARATOR = Buffer.from('PRESALE_V1');
const PAYMENT_SOL = 0;
const PAYMENT_USDT = 1;
const PAYMENT_USDC = 2;

interface SignatureParams {
  programId: PublicKey;
  buyer: PublicKey;
  paymentMint: PublicKey;
  paymentType: number;
  paymentAmount: bigint;
  tokenAmount: bigint;
  nonce: bigint;
}

function constructMessage(params: SignatureParams): Buffer {
  const message = Buffer.alloc(131);
  let offset = 0;

  // Domain separator (10 bytes)
  DOMAIN_SEPARATOR.copy(message, offset);
  offset += 10;

  // Program ID (32 bytes)
  params.programId.toBuffer().copy(message, offset);
  offset += 32;

  // Buyer (32 bytes)
  params.buyer.toBuffer().copy(message, offset);
  offset += 32;

  // Payment mint (32 bytes)
  params.paymentMint.toBuffer().copy(message, offset);
  offset += 32;

  // Payment type (1 byte)
  message.writeUInt8(params.paymentType, offset);
  offset += 1;

  // Payment amount (8 bytes, little-endian)
  message.writeBigUInt64LE(params.paymentAmount, offset);
  offset += 8;

  // Token amount (8 bytes, little-endian)
  message.writeBigUInt64LE(params.tokenAmount, offset);
  offset += 8;

  // Nonce (8 bytes, little-endian)
  message.writeBigUInt64LE(params.nonce, offset);

  return message;
}

function signPurchaseAuthorization(
  authorizedSigner: Keypair,
  params: SignatureParams
): { signature: Uint8Array; message: Buffer } {
  const message = constructMessage(params);
  const signature = nacl.sign.detached(message, authorizedSigner.secretKey);
  
  return { signature, message };
}

// Example usage:
const authorizedSigner = Keypair.generate(); // Your authorized signer keypair
const programId = new PublicKey('Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS');
const buyer = new PublicKey('BuyerWalletAddressHere...');
const usdtMint = new PublicKey('USDTMintAddressHere...');

const { signature, message } = signPurchaseAuthorization(authorizedSigner, {
  programId,
  buyer,
  paymentMint: usdtMint,
  paymentType: PAYMENT_USDT,
  paymentAmount: BigInt(100_000_000), // 100 USDT (6 decimals)
  tokenAmount: BigInt(1000_000_000_000), // 1000 tokens (9 decimals)
  nonce: BigInt(Date.now()), // Use timestamp or counter as nonce
});
```

### Building the Transaction

```typescript
import {
  Transaction,
  Ed25519Program,
  TransactionInstruction,
} from '@solana/web3.js';

function buildPurchaseTransaction(
  buyer: PublicKey,
  signature: Uint8Array,
  message: Buffer,
  authorizedSignerPubkey: PublicKey,
  // ... other accounts
): Transaction {
  const tx = new Transaction();

  // 1. Add ed25519 signature verification instruction FIRST
  const ed25519Ix = Ed25519Program.createInstructionWithPublicKey({
    publicKey: authorizedSignerPubkey.toBytes(),
    message: message,
    signature: signature,
  });
  tx.add(ed25519Ix);

  // 2. Add buy_tokens instruction
  const buyTokensIx = new TransactionInstruction({
    programId: PRESALE_PROGRAM_ID,
    keys: [
      { pubkey: buyer, isSigner: true, isWritable: true },
      { pubkey: configPda, isSigner: false, isWritable: true },
      { pubkey: paymentMint, isSigner: false, isWritable: false },
      { pubkey: buyerPaymentAccount, isSigner: false, isWritable: true },
      { pubkey: treasuryPaymentAccount, isSigner: false, isWritable: true },
      { pubkey: vestingAccount, isSigner: false, isWritable: true },
      { pubkey: nonceAccount, isSigner: false, isWritable: true },
      { pubkey: SYSVAR_INSTRUCTIONS_PUBKEY, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data: encodeBuyTokensData(paymentAmount, tokenAmount, nonce, signature),
  });
  tx.add(buyTokensIx);

  return tx;
}
```

## Vesting Schedule

### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `vesting_start_time` | i64 | Unix timestamp when vesting begins |
| `cliff_duration` | i64 | Seconds after start before any tokens vest |
| `vesting_duration` | i64 | Total vesting period in seconds (includes cliff) |

### Vesting Timeline

```
                    cliff_end                    vesting_end
                        │                             │
    vesting_start       │                             │
         │              │                             │
         ▼              ▼                             ▼
─────────┬──────────────┬─────────────────────────────┬──────────▶ time
         │              │                             │
         │◀────────────▶│◀───────────────────────────▶│
         │    cliff     │      linear vesting         │
         │              │                             │
         │  0% vested   │   proportional vesting      │ 100% vested
```

### Vesting Calculation

```
cliff_end = vesting_start_time + cliff_duration
vesting_end = vesting_start_time + vesting_duration

if current_time < cliff_end:
    vested_amount = 0
elif current_time >= vesting_end:
    vested_amount = total_purchased
else:
    elapsed = current_time - cliff_end
    vesting_period = vesting_end - cliff_end
    vested_amount = total_purchased * elapsed / vesting_period

claimable = vested_amount - already_claimed
```

## Security Considerations

### 1. Signature Replay Protection

- **Nonce Tracking**: Each nonce is stored in a PDA derived from `[NONCE_SEED, buyer, nonce_bytes]`
- **Single Use**: Once a nonce is used, the account's `is_used` flag is set to `true`
- **Unique Per Transaction**: The nonce must be unique for each purchase transaction
- **Recommended Nonce Strategy**: Use monotonically increasing counter or timestamp

### 2. Domain Separation

- **Purpose**: Prevents signatures from being valid across different programs
- **Implementation**: `DOMAIN_SEPARATOR = "PRESALE_V1"` is included in every signed message
- **Program ID**: Also included in the message to bind signatures to this specific deployment

### 3. Account Validation

All accounts are validated using Anchor constraints:

```rust
// Payment mint must be USDT or USDC
#[account(
    constraint = payment_mint.key() == config.usdt_mint || 
                 payment_mint.key() == config.usdc_mint 
)]
pub payment_mint: Account<'info, Mint>,

// Treasury account must match config
#[account(
    constraint = treasury_payment_account.owner == config.treasury
)]
pub treasury_payment_account: Account<'info, TokenAccount>,
```

### 4. Arithmetic Safety

- All arithmetic operations use `checked_*` methods
- Intermediate calculations use `u128` to prevent overflow
- Results are validated before casting back to `u64`

### 5. Authorization Checks

- **Admin Functions**: `initialize`, `update_config`, `deposit_tokens`, `withdraw_tokens` require admin signature
- **Purchase Functions**: Require valid ed25519 signature from authorized signer
- **Claim Function**: Only the vesting account owner can claim their tokens

### 6. Treasury Security

- Payments go directly to treasury wallet
- Program never holds payment funds
- Treasury address stored in config PDA (can be updated by admin)

## Edge Cases

### 1. Multiple Purchases

- Users can make multiple purchases
- Each purchase accumulates in `vesting_account.total_purchased`
- All purchases share the same vesting schedule

### 2. Partial Claims

- Users can claim multiple times as tokens vest
- `claimed_amount` tracks total claimed
- `claimable = vested - claimed`

### 3. Presale Deactivation

- Admin can set `is_active = false` to pause purchases
- Claims still work when presale is inactive
- Prevents new purchases without affecting existing vestings

### 4. Price Changes

- Admin can update `token_price_per_unit`
- Only affects future purchases
- Existing vesting accounts unaffected

### 5. Zero Cliff

- Setting `cliff_duration = 0` means linear vesting starts immediately
- Tokens begin vesting from `vesting_start_time`

### 6. Vault Underfunding

- If vault has insufficient tokens, claim will fail
- Admin must ensure vault is funded before vesting begins
- `deposit_tokens` instruction provided for this purpose

## Deployment Checklist

1. **Deploy Program**
   ```bash
   anchor build
   anchor deploy
   ```

2. **Initialize Config**
   - Set treasury wallet address
   - Set authorized signer public key
   - Configure USDT/USDC mint addresses
   - Set token price
   - Configure vesting schedule

3. **Fund Vault**
   - Calculate total tokens needed for presale
   - Call `deposit_tokens` with sufficient amount

4. **Set Up Off-Chain Signer**
   - Securely store authorized signer private key
   - Implement signature API endpoint
   - Implement nonce generation/tracking

5. **Create Treasury Token Accounts**
   - Create associated token accounts for USDT/USDC
   - Ensure treasury wallet can receive SOL

## Testing

```bash
# Build the program
anchor build

# Run tests
anchor test

# Deploy to devnet
anchor deploy --provider.cluster devnet
```

## License

MIT
