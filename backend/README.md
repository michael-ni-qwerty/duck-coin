# DuckCoin Presale Backend API

FastAPI backend for the DuckCoin token presale system with **multi-chain support**. Designed with a scalable architecture to easily add new blockchains.

## Features

- **Multi-Chain Support**: Blockchain-agnostic architecture supporting multiple chains
  - ✅ Solana (ed25519 signatures)
  - 🔜 Ethereum (EIP-712 typed data)
  - 🔜 Tron (secp256k1 signatures)
  - 🔜 BSC, Polygon, and more
- **Purchase Authorization**: Generate chain-specific signed authorizations
- **Nonce Management**: Unique nonce generation with Redis tracking and on-chain verification
- **Vesting Queries**: Query vesting information for any wallet on any chain
- **Presale Stats**: Get presale configuration and statistics per chain

## Setup

### Prerequisites

- Python 3.10+
- Redis (for nonce tracking)
- PostgreSQL (optional, for persistent storage)

### Installation

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
```

### Configuration

Edit `.env` file with your settings:

```env
# Solana Configuration
SOLANA_RPC_URL=https://api.devnet.solana.com
PRESALE_PROGRAM_ID=<your-program-id>

# Token Mints
PRESALE_TOKEN_MINT=<presale-token-mint>
USDT_MINT=<usdt-mint-address>
USDC_MINT=<usdc-mint-address>

# Treasury
TREASURY_WALLET=<treasury-wallet-address>

# CRITICAL: Authorized Signer Private Key (Base58 encoded)
# This key signs all purchase authorizations
AUTHORIZED_SIGNER_PRIVATE_KEY=<base58-private-key>

# Redis
REDIS_URL=redis://localhost:6379/0
```

### Running

```bash
# Development
python run.py

# Or with uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Health

- `GET /health` - Basic health check
- `GET /ready` - Readiness check (verifies dependencies)

### Presale

- `POST /api/v1/presale/authorize-purchase` - Generate purchase authorization
- `GET /api/v1/presale/config` - Get presale configuration
- `POST /api/v1/presale/vesting-info` - Get vesting info for a wallet
- `GET /api/v1/presale/stats` - Get presale statistics
- `GET /api/v1/presale/payment-mints` - Get accepted payment token mints
- `GET /api/v1/presale/pda-addresses/{wallet}` - Get PDA addresses for transaction building

## Purchase Flow

### 1. Request Authorization

```bash
curl -X POST http://localhost:8000/api/v1/presale/authorize-purchase \
  -H "Content-Type: application/json" \
  -d '{
    "buyer_wallet": "BuyerWalletAddressHere",
    "payment_type": "USDT",
    "payment_amount": 100000000,
    "token_amount": 1000000000000
  }'
```

Response:
```json
{
  "buyer_wallet": "BuyerWalletAddressHere",
  "payment_type": "USDT",
  "payment_mint": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
  "payment_amount": 100000000,
  "token_amount": 1000000000000,
  "nonce": 1234567890123456789,
  "signature": "Base58EncodedSignature",
  "message": "Base58EncodedMessage",
  "authorized_signer_pubkey": "AuthorizedSignerPubkey"
}
```

### 2. Build Transaction (Client-Side)

```typescript
import { Ed25519Program, Transaction } from '@solana/web3.js';
import base58 from 'bs58';

// Decode signature and message from API response
const signature = base58.decode(response.signature);
const message = base58.decode(response.message);
const signerPubkey = new PublicKey(response.authorized_signer_pubkey);

// Build transaction
const tx = new Transaction();

// 1. Add ed25519 verification instruction FIRST
tx.add(
  Ed25519Program.createInstructionWithPublicKey({
    publicKey: signerPubkey.toBytes(),
    message: message,
    signature: signature,
  })
);

// 2. Add buy_tokens instruction
tx.add(buyTokensInstruction);

// 3. Submit transaction
await sendAndConfirmTransaction(connection, tx, [buyerKeypair]);
```

## Security Considerations

### Authorized Signer Key

- **NEVER** commit the private key to version control
- Use environment variables or secrets management
- Rotate keys periodically
- Monitor for unauthorized usage

### Nonce Management

- Nonces are tracked in Redis for fast lookup
- On-chain verification is the source of truth
- Each nonce can only be used once
- Nonces expire from Redis after 24 hours

### Rate Limiting

Consider adding rate limiting in production:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/authorize-purchase")
@limiter.limit("10/minute")
async def authorize_purchase(...):
    ...
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
# Format
black app/
isort app/

# Lint
ruff check app/
mypy app/
```

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t duckcoin-api .
docker run -p 8000:8000 --env-file .env duckcoin-api
```

## License

MIT
