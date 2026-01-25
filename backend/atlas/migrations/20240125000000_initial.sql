-- Initial migration: Create presale tables
-- Generated for Atlas migration system

-- Purchases table: Records of token purchases across all chains
CREATE TABLE IF NOT EXISTS purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain VARCHAR(20) NOT NULL,
    buyer_wallet VARCHAR(128) NOT NULL,
    payment_type VARCHAR(20) NOT NULL,
    payment_token_address VARCHAR(128),
    payment_amount BIGINT NOT NULL,
    token_amount BIGINT NOT NULL,
    nonce BIGINT NOT NULL,
    signature TEXT NOT NULL,
    tx_hash VARCHAR(128),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

CREATE INDEX idx_purchases_chain ON purchases(chain);
CREATE INDEX idx_purchases_buyer_wallet ON purchases(buyer_wallet);
CREATE INDEX idx_purchases_tx_hash ON purchases(tx_hash);
CREATE INDEX idx_purchases_chain_buyer ON purchases(chain, buyer_wallet);
CREATE INDEX idx_purchases_chain_status ON purchases(chain, status);

-- Vesting cache table
CREATE TABLE IF NOT EXISTS vesting_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain VARCHAR(20) NOT NULL,
    wallet_address VARCHAR(128) NOT NULL,
    total_purchased BIGINT NOT NULL DEFAULT 0,
    claimed_amount BIGINT NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    on_chain_address VARCHAR(128),
    UNIQUE(chain, wallet_address)
);

CREATE INDEX idx_vesting_cache_chain ON vesting_cache(chain);
CREATE INDEX idx_vesting_cache_wallet ON vesting_cache(wallet_address);

-- Nonce records table
CREATE TABLE IF NOT EXISTS nonce_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain VARCHAR(20) NOT NULL,
    wallet_address VARCHAR(128) NOT NULL,
    nonce BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    UNIQUE(chain, wallet_address, nonce)
);

CREATE INDEX idx_nonce_records_chain ON nonce_records(chain);
CREATE INDEX idx_nonce_records_wallet ON nonce_records(wallet_address);

-- Presale stats table
CREATE TABLE IF NOT EXISTS presale_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain VARCHAR(20) NOT NULL UNIQUE,
    total_sold BIGINT NOT NULL DEFAULT 0,
    total_participants INTEGER NOT NULL DEFAULT 0,
    total_raised_native BIGINT NOT NULL DEFAULT 0,
    total_raised_usdt BIGINT NOT NULL DEFAULT 0,
    total_raised_usdc BIGINT NOT NULL DEFAULT 0,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Check constraints for data integrity
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_payment_type 
    CHECK (payment_type IN ('native', 'usdt', 'usdc'));
ALTER TABLE purchases ADD CONSTRAINT chk_purchases_status 
    CHECK (status IN ('pending', 'confirmed', 'failed'));

ALTER TABLE vesting_cache ADD CONSTRAINT chk_vesting_cache_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));

ALTER TABLE nonce_records ADD CONSTRAINT chk_nonce_records_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));
ALTER TABLE nonce_records ADD CONSTRAINT chk_nonce_records_status 
    CHECK (status IN ('pending', 'used', 'expired'));

ALTER TABLE presale_stats ADD CONSTRAINT chk_presale_stats_chain 
    CHECK (chain IN ('solana', 'ethereum', 'tron', 'bsc', 'polygon'));
