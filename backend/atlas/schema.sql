-- DuckCoin Presale Database Schema
-- This file is the source of truth for Atlas migrations
-- Run: atlas migrate diff --env local

-- Purchases table: Records of token purchases across all chains
CREATE TABLE IF NOT EXISTS purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Blockchain info
    chain VARCHAR(20) NOT NULL,
    
    -- Wallet info
    buyer_wallet VARCHAR(128) NOT NULL,
    
    -- Payment details
    payment_type VARCHAR(20) NOT NULL,
    payment_token_address VARCHAR(128),
    payment_amount BIGINT NOT NULL,
    
    -- Token details
    token_amount BIGINT NOT NULL,
    
    -- Authorization
    nonce BIGINT NOT NULL,
    signature TEXT NOT NULL,
    
    -- Transaction
    tx_hash VARCHAR(128),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

-- Indexes for purchases
CREATE INDEX IF NOT EXISTS idx_purchases_chain ON purchases(chain);
CREATE INDEX IF NOT EXISTS idx_purchases_buyer_wallet ON purchases(buyer_wallet);
CREATE INDEX IF NOT EXISTS idx_purchases_tx_hash ON purchases(tx_hash);
CREATE INDEX IF NOT EXISTS idx_purchases_chain_buyer ON purchases(chain, buyer_wallet);
CREATE INDEX IF NOT EXISTS idx_purchases_chain_status ON purchases(chain, status);

-- Vesting cache: Cached vesting information from on-chain
CREATE TABLE IF NOT EXISTS vesting_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Blockchain info
    chain VARCHAR(20) NOT NULL,
    
    -- Wallet
    wallet_address VARCHAR(128) NOT NULL,
    
    -- Vesting data (from on-chain)
    total_purchased BIGINT NOT NULL DEFAULT 0,
    claimed_amount BIGINT NOT NULL DEFAULT 0,
    
    -- Cache metadata
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    on_chain_address VARCHAR(128),
    
    -- Unique constraint
    UNIQUE(chain, wallet_address)
);

-- Indexes for vesting_cache
CREATE INDEX IF NOT EXISTS idx_vesting_cache_chain ON vesting_cache(chain);
CREATE INDEX IF NOT EXISTS idx_vesting_cache_wallet ON vesting_cache(wallet_address);

-- Nonce records: Persistent nonce tracking for replay protection
CREATE TABLE IF NOT EXISTS nonce_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Blockchain info
    chain VARCHAR(20) NOT NULL,
    
    -- Wallet
    wallet_address VARCHAR(128) NOT NULL,
    
    -- Nonce
    nonce BIGINT NOT NULL,
    
    -- Status: pending, used, expired
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    
    -- Unique constraint
    UNIQUE(chain, wallet_address, nonce)
);

-- Indexes for nonce_records
CREATE INDEX IF NOT EXISTS idx_nonce_records_chain ON nonce_records(chain);
CREATE INDEX IF NOT EXISTS idx_nonce_records_wallet ON nonce_records(wallet_address);

-- Presale stats: Aggregated presale statistics per chain
CREATE TABLE IF NOT EXISTS presale_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Blockchain info (unique per chain)
    chain VARCHAR(20) NOT NULL UNIQUE,
    
    -- Stats
    total_sold BIGINT NOT NULL DEFAULT 0,
    total_participants INTEGER NOT NULL DEFAULT 0,
    total_raised_native BIGINT NOT NULL DEFAULT 0,
    total_raised_usdt BIGINT NOT NULL DEFAULT 0,
    total_raised_usdc BIGINT NOT NULL DEFAULT 0,
    
    -- Timestamps
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enum-like check constraints for data integrity
ALTER TABLE purchases DROP CONSTRAINT IF EXISTS chk_purchases_chain;
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));

ALTER TABLE purchases DROP CONSTRAINT IF EXISTS chk_purchases_payment_type;
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_payment_type 
    CHECK (payment_type IN ('native', 'usdt', 'usdc'));

ALTER TABLE purchases DROP CONSTRAINT IF EXISTS chk_purchases_status;
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_status 
    CHECK (status IN ('pending', 'confirmed', 'failed'));

ALTER TABLE vesting_cache DROP CONSTRAINT IF EXISTS chk_vesting_cache_chain;
ALTER TABLE vesting_cache ADD CONSTRAINT chk_vesting_cache_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));

ALTER TABLE nonce_records DROP CONSTRAINT IF EXISTS chk_nonce_records_chain;
ALTER TABLE nonce_records ADD CONSTRAINT chk_nonce_records_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));

ALTER TABLE nonce_records DROP CONSTRAINT IF EXISTS chk_nonce_records_status;
ALTER TABLE nonce_records ADD CONSTRAINT chk_nonce_records_status 
    CHECK (status IN ('pending', 'used', 'expired'));

ALTER TABLE presale_stats DROP CONSTRAINT IF EXISTS chk_presale_stats_chain;
ALTER TABLE presale_stats ADD CONSTRAINT chk_presale_stats_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));
