-- DuckCoin Database Schema
-- This file is the source of truth for Atlas migrations

-- Blockchains table
CREATE TABLE IF NOT EXISTS blockchains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    symbol VARCHAR(10) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    extra_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tokens table
CREATE TABLE IF NOT EXISTS tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blockchain_id UUID NOT NULL REFERENCES blockchains(id),
    address VARCHAR(128), -- NULL for native tokens
    symbol VARCHAR(20) NOT NULL,
    decimals INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    extra_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(blockchain_id, address)
);

-- Addresses table
CREATE TABLE IF NOT EXISTS addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blockchain_id UUID NOT NULL REFERENCES blockchains(id),
    address VARCHAR(128) NOT NULL,
    label VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(blockchain_id, address)
);

-- Transactions table (formerly purchases)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Transaction type: 'payment', 'transfer', etc.
    type VARCHAR(20) NOT NULL DEFAULT 'payment',
    
    -- Blockchain and Token info
    blockchain_id UUID NOT NULL REFERENCES blockchains(id),
    token_id UUID REFERENCES tokens(id), -- NULL if native
    
    -- Wallet info
    from_address_id VARCHAR(128),
    to_address_id VARCHAR(128),
    
    -- Details
    amount BIGINT NOT NULL,
    tx_hash VARCHAR(128),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Metadata (can be used for purchase specific details)
    metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_blockchain_id ON transactions(blockchain_id);
CREATE INDEX IF NOT EXISTS idx_transactions_token_id ON transactions(token_id);
CREATE INDEX IF NOT EXISTS idx_transactions_from_address_id ON transactions(from_address_id);
CREATE INDEX IF NOT EXISTS idx_transactions_tx_hash ON transactions(tx_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);

-- Constraints
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_status;
ALTER TABLE transactions ADD CONSTRAINT chk_transactions_status 
    CHECK (status IN ('pending', 'confirmed', 'failed'));

ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_type;
ALTER TABLE transactions ADD CONSTRAINT chk_transactions_type 
    CHECK (type IN ('payment'));
