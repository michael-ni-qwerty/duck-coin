-- Create "blockchains" table
CREATE TABLE "blockchains" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "name" character varying(50) NOT NULL,
  "symbol" character varying(10) NOT NULL,
  "is_active" boolean NOT NULL DEFAULT true,
  "extra_data" jsonb NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "blockchains_name_key" UNIQUE ("name")
);
-- Create "addresses" table
CREATE TABLE "addresses" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "blockchain_id" uuid NOT NULL,
  "address" character varying(128) NOT NULL,
  "label" character varying(100) NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "addresses_blockchain_id_address_key" UNIQUE ("blockchain_id", "address"),
  CONSTRAINT "addresses_blockchain_id_fkey" FOREIGN KEY ("blockchain_id") REFERENCES "blockchains" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "tokens" table
CREATE TABLE "tokens" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "blockchain_id" uuid NOT NULL,
  "address" character varying(128) NULL,
  "symbol" character varying(20) NOT NULL,
  "decimals" integer NOT NULL,
  "is_active" boolean NOT NULL DEFAULT true,
  "extra_data" jsonb NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "tokens_blockchain_id_address_key" UNIQUE ("blockchain_id", "address"),
  CONSTRAINT "tokens_blockchain_id_fkey" FOREIGN KEY ("blockchain_id") REFERENCES "blockchains" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "transactions" table
CREATE TABLE "transactions" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "type" character varying(20) NOT NULL DEFAULT 'payment',
  "blockchain_id" uuid NOT NULL,
  "token_id" uuid NULL,
  "from_address_id" character varying(128) NULL,
  "to_address_id" character varying(128) NULL,
  "amount" bigint NOT NULL,
  "tx_hash" character varying(128) NULL,
  "status" character varying(20) NOT NULL DEFAULT 'pending',
  "metadata" jsonb NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "confirmed_at" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "transactions_blockchain_id_fkey" FOREIGN KEY ("blockchain_id") REFERENCES "blockchains" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "transactions_token_id_fkey" FOREIGN KEY ("token_id") REFERENCES "tokens" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "chk_transactions_status" CHECK ((status)::text = ANY ((ARRAY['pending'::character varying, 'confirmed'::character varying, 'failed'::character varying])::text[])),
  CONSTRAINT "chk_transactions_type" CHECK ((type)::text = 'payment'::text)
);
-- Create index "idx_transactions_blockchain_id" to table: "transactions"
CREATE INDEX "idx_transactions_blockchain_id" ON "transactions" ("blockchain_id");
-- Create index "idx_transactions_from_address_id" to table: "transactions"
CREATE INDEX "idx_transactions_from_address_id" ON "transactions" ("from_address_id");
-- Create index "idx_transactions_status" to table: "transactions"
CREATE INDEX "idx_transactions_status" ON "transactions" ("status");
-- Create index "idx_transactions_token_id" to table: "transactions"
CREATE INDEX "idx_transactions_token_id" ON "transactions" ("token_id");
-- Create index "idx_transactions_tx_hash" to table: "transactions"
CREATE INDEX "idx_transactions_tx_hash" ON "transactions" ("tx_hash");
-- Create index "idx_transactions_type" to table: "transactions"
CREATE INDEX "idx_transactions_type" ON "transactions" ("type");
