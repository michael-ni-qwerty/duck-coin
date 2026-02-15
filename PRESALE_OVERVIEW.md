# DuckCoin Presale — How It Works

## Overview

DuckCoin runs a **non-custodial token presale** on Solana. Investors pay with any cryptocurrency via NOWPayments, and their token allocation is recorded on-chain. After the presale ends and the token launches, investors claim their tokens in two stages: an immediate TGE (Token Generation Event) portion and a gradually unlocked vesting portion.

No user accounts, no KYC, no custody — just a wallet address.

---

## Architecture

```
┌──────────┐      ┌──────────────┐      ┌────────────────┐      ┌──────────────────┐
│ Frontend  │─────▶│  Backend API │─────▶│  NOWPayments   │      │  Solana Program  │
│ (wallet)  │      │  (FastAPI)   │◀─────│  (IPN webhook) │      │  (on-chain)      │
└──────────┘      └──────┬───────┘      └────────────────┘      └────────┬─────────┘
                         │                                               │
                         │         credit_allocation (after payment)     │
                         └───────────────────────────────────────────────┘
```

**Components:**

- **Frontend** — Connects user's Solana wallet, sends purchase requests
- **Backend (FastAPI + PostgreSQL)** — Manages payments, talks to NOWPayments and Solana
- **NOWPayments** — Third-party payment processor accepting 200+ cryptocurrencies
- **Solana Program (Anchor)** — On-chain presale logic: allocations, config, claiming

---

## Purchase Flow

### 1. Investor initiates purchase

The investor connects their Solana wallet and chooses a USD amount to invest.

**Frontend → Backend:** `POST /api/v1/presale/create-invoice`
```json
{
  "wallet_address": "ABC...xyz",
  "usd_amount": 100
}
```

The backend:
- Looks up today's token price from the tokenomics schedule
- Calculates how many tokens the investor will receive
- Creates a NOWPayments invoice
- Saves a `Payment` record in the database (status: `waiting`)
- Returns the invoice URL to the frontend

### 2. Investor pays

The investor is redirected to NOWPayments' hosted payment page where they can pay with BTC, ETH, USDT, SOL, or any of 200+ supported cryptocurrencies.

### 3. Payment confirmation

When the payment is confirmed, NOWPayments sends an **IPN (Instant Payment Notification)** webhook to the backend.

**NOWPayments → Backend:** `POST /api/v1/presale/ipn-webhook`

The backend:
- Verifies the HMAC signature to prevent spoofing
- Updates the payment record status (`confirming` → `finished`)
- On `finished` status: calls `credit_allocation` on the Solana program

### 4. On-chain credit

The backend's admin wallet signs a `credit_allocation` transaction on Solana:
- Records the investor's token allocation on-chain (PDA per wallet)
- Splits the allocation into **TGE portion** (immediately claimable) and **vesting portion** (locked)
- Updates global counters: `total_sold`, `total_raised_usd`, `sold_today`

### 5. Investor record

After successful on-chain credit, the backend upserts an `Investor` record in the database:
- Tracks cumulative `total_invested_usd`, `total_tokens`, `payment_count`
- Stores `first_invested_at` and `last_invested_at` timestamps
- Has a flexible `extra_data` JSON field for any future metadata

---

## Tokenomics Schedule

The presale runs for **150 days** with a hardcoded schedule. Each day has:

| Parameter | Description |
|---|---|
| **Price** | Token price in USD (increases over time) |
| **TGE %** | Percentage of purchased tokens claimable at token launch (decreases over time) |
| **Daily Cap** | Maximum tokens available for sale that day |

A **daily config worker** runs at 00:05 UTC each day:
1. Computes which presale day it is (from `PRESALE_START_DATE`)
2. Looks up that day's price, TGE %, and daily cap from the schedule
3. Calls `update_config` on the Solana program

This transaction also:
- Burns any unsold tokens from the previous day
- Resets the daily sold counter
- Advances the on-chain day tracker

When the schedule ends (day > 150), the worker sends `daily_cap = 0`, which automatically sets the presale status to `PresaleEnded`.

---

## On-Chain State

### PresaleConfig (single global account)

| Field | Description |
|---|---|
| `admin` | Admin wallet (signs all privileged transactions) |
| `token_mint` | SPL token mint address |
| `token_price_usd` | Current price (with 10^9 precision) |
| `tge_percentage` | Current TGE % for new purchases |
| `daily_cap` | Max tokens sellable today |
| `total_sold` | Cumulative tokens sold across all days |
| `presale_supply` | Total presale allocation (2.4B tokens) |
| `total_burned` | Cumulative unsold tokens burned |
| `status` | `PresaleActive` → `PresaleEnded` → `TokenLaunched` |
| `total_raised_usd` | Cumulative USD raised |
| `global_unlock_pct` | Vesting unlock percentage (0–100%) |

### UserAllocation (one PDA per investor wallet)

| Field | Description |
|---|---|
| `amount_purchased` | Total tokens ever purchased |
| `amount_claimed` | Total tokens already withdrawn |
| `claimable_amount` | Tokens available to claim right now |
| `amount_vesting` | Non-TGE tokens (basis for vesting unlock) |
| `last_unlock_pct` | Last global unlock % applied to this user |

---

## Two-Stage Token Claiming

### Stage 1: TGE Claim

After the presale ends, the admin sets the status to `TokenLaunched`. Investors can immediately claim their **TGE portion** — the percentage of tokens that was locked in at the time of each purchase.

**Example:** An investor buys 1,000 tokens on Day 1 when TGE = 50%.
- 500 tokens are immediately claimable after token launch
- 500 tokens are locked in the vesting pool

### Stage 2: Vesting Unlock

After TGE, the admin gradually unlocks the remaining tokens by calling `set_unlock`:

```
set_unlock(25)  →  25% of vesting pool becomes claimable
set_unlock(50)  →  another 25% unlocked (50% total)
set_unlock(100) →  all remaining tokens unlocked
```

This is a **global setting** — one transaction unlocks tokens for all investors simultaneously. Each investor's share is computed proportionally from their `amount_vesting` when they call `claim`.

**Example continued:**
| Admin action | Investor's new claimable | Cumulative claimed |
|---|---|---|
| Token launch (TGE 50%) | 500 | 500 |
| `set_unlock(25)` | 125 (25% of 500 vesting) | 625 |
| `set_unlock(50)` | 125 | 750 |
| `set_unlock(100)` | 250 | 1,000 |

The unlock percentage can only increase — it cannot be decreased once set.

---

## Admin Operations

| Action | Instruction | When |
|---|---|---|
| Initialize presale | `initialize` | Once, at deployment |
| Daily rollover | `update_config` | Automated daily at 00:05 UTC |
| End presale | `set_status(PresaleEnded)` | After last day (or manual) |
| Launch token | `set_status(TokenLaunched)` | When token is ready |
| Unlock vesting | `set_unlock(pct)` | Post-launch, gradual |

---

## API Endpoints

### Investor-facing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/presale/create-invoice` | Create payment invoice |
| `GET` | `/presale/payment/{id}` | Check payment status |
| `GET` | `/presale/payments/{wallet}` | List all payments for a wallet |
| `GET` | `/presale/allocation/{wallet}` | Get on-chain token allocation |
| `GET` | `/presale/config` | Get current presale config |
| `GET` | `/presale/stats` | Get presale statistics |
| `GET` | `/presale/estimate` | Estimate crypto amount for USD |
| `GET` | `/presale/currencies` | List accepted cryptocurrencies |

### Investor profile

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/presale/investor/{wallet}` | Get investor aggregate data |
| `PATCH` | `/presale/investor/{wallet}` | Update investor extra data |
| `GET` | `/presale/investors` | List all investors (sortable) |

---

## Security

- **Non-custodial** — The backend never holds user funds or private keys
- **HMAC verification** — All NOWPayments webhooks are signature-verified
- **Admin-only on-chain** — `credit_allocation`, `update_config`, `set_status`, and `set_unlock` require the admin wallet signature
- **Invariants enforced on-chain:**
  - Token price can only increase
  - TGE percentage can only decrease
  - Daily cap can only decrease
  - Unlock percentage can only increase
  - Supply limits are checked on every purchase
  - Daily caps are enforced per day

---

## Database

### Payments table
Tracks every individual payment: wallet, USD amount, token amount, NOWPayments IDs, payment status, credit status, and transaction signatures.

### Investors table
Aggregated per-wallet data: total invested USD, total tokens, payment count, timestamps, and a flexible `extra_data` JSON field for any future needs.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Smart contract | Solana (Anchor 0.29) |
| Backend | Python (FastAPI + Tortoise ORM) |
| Database | PostgreSQL |
| Migrations | Atlas |
| Payments | NOWPayments API |
| Token standard | SPL Token |
