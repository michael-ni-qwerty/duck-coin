-- DuckCoin Database Schema
-- This file is the source of truth for Atlas migrations
-- Updated for NOWPayments integration (Solana-only)

-- Payments table: tracks NOWPayments invoices and on-chain credit status
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- User info
    wallet_address VARCHAR(128) NOT NULL,
    claim_wallet_solana VARCHAR(128),

    -- NOWPayments data
    nowpayments_invoice_id VARCHAR(64),
    nowpayments_payment_id BIGINT UNIQUE,
    nowpayments_order_id VARCHAR(128),

    -- Amounts
    price_amount_usd NUMERIC(18, 2) NOT NULL,
    token_amount BIGINT NOT NULL,
    pay_amount NUMERIC(28, 12),
    pay_currency VARCHAR(20),
    actually_paid NUMERIC(28, 12),

    -- Referral tracking
    referral_code VARCHAR(32),
    referral_reward_usd NUMERIC(18, 2) DEFAULT 0,
    referral_reward_tokens BIGINT DEFAULT 0,

    -- Status
    payment_status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    credit_status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- On-chain credit
    credit_tx_signature VARCHAR(128),
    credit_error TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ,
    credited_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_payments_wallet_address ON payments(wallet_address);
CREATE INDEX IF NOT EXISTS idx_payments_claim_wallet_solana ON payments(claim_wallet_solana);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(nowpayments_invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(nowpayments_order_id);
CREATE INDEX IF NOT EXISTS idx_payments_payment_status ON payments(payment_status);
CREATE INDEX IF NOT EXISTS idx_payments_credit_status ON payments(credit_status);

-- Constraints
ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_payment_status;
ALTER TABLE payments ADD CONSTRAINT chk_payment_status
    CHECK (payment_status IN (
        'waiting', 'confirming', 'confirmed', 'sending',
        'partially_paid', 'finished', 'failed', 'refunded', 'expired'
    ));

ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_credit_status;
ALTER TABLE payments ADD CONSTRAINT chk_credit_status
    CHECK (credit_status IN ('pending', 'credited', 'failed'));

-- Investors table: aggregated per-wallet investment data
CREATE TABLE IF NOT EXISTS investors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address VARCHAR(128) NOT NULL UNIQUE,

    -- Aggregated totals (updated on each credited payment)
    total_invested_usd NUMERIC(18, 2) NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    launching_tokens BIGINT NOT NULL DEFAULT 0,
    payment_count INTEGER NOT NULL DEFAULT 0,

    -- Referral System
    referral_code VARCHAR(32) UNIQUE,
    referred_by VARCHAR(128) REFERENCES investors(wallet_address),
    total_referral_earnings_usd NUMERIC(18, 2) NOT NULL DEFAULT 0,
    total_referral_earnings_tokens BIGINT NOT NULL DEFAULT 0,
    referral_count INTEGER NOT NULL DEFAULT 0,

    -- Flexible metadata
    extra_data JSONB NOT NULL DEFAULT '{}',

    -- First / last activity
    first_invested_at TIMESTAMPTZ,
    last_invested_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_investors_wallet_address ON investors(wallet_address);

-- AuthMessages table: stores nonces for wallet signature verification
CREATE TABLE IF NOT EXISTS auth_messages (
    wallet_address VARCHAR(128) PRIMARY KEY,
    message VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);
