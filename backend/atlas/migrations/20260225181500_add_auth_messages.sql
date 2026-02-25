-- Modify "payments" table
ALTER TABLE "payments" ADD COLUMN "claim_wallet_solana" character varying(128) NULL;
-- Create index "idx_payments_claim_wallet_solana" to table: "payments"
CREATE INDEX "idx_payments_claim_wallet_solana" ON "payments" ("claim_wallet_solana");
-- Create "auth_messages" table
CREATE TABLE "auth_messages" (
  "wallet_address" character varying(128) NOT NULL,
  "message" character varying(255) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "expires_at" timestamptz NOT NULL,
  PRIMARY KEY ("wallet_address")
);
