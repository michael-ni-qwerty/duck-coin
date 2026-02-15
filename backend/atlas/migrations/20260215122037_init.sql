-- Create "investors" table
CREATE TABLE "investors" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "wallet_address" character varying(128) NOT NULL,
  "total_invested_usd" numeric(18,2) NOT NULL DEFAULT 0,
  "total_tokens" bigint NOT NULL DEFAULT 0,
  "payment_count" integer NOT NULL DEFAULT 0,
  "extra_data" jsonb NOT NULL DEFAULT '{}',
  "first_invested_at" timestamptz NULL,
  "last_invested_at" timestamptz NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "investors_wallet_address_key" UNIQUE ("wallet_address")
);
-- Create index "idx_investors_wallet_address" to table: "investors"
CREATE INDEX "idx_investors_wallet_address" ON "investors" ("wallet_address");
-- Create "payments" table
CREATE TABLE "payments" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "wallet_address" character varying(128) NOT NULL,
  "nowpayments_invoice_id" character varying(64) NULL,
  "nowpayments_payment_id" bigint NULL,
  "nowpayments_order_id" character varying(128) NULL,
  "price_amount_usd" numeric(18,2) NOT NULL,
  "token_amount" bigint NOT NULL,
  "pay_amount" numeric(28,12) NULL,
  "pay_currency" character varying(20) NULL,
  "actually_paid" numeric(28,12) NULL,
  "payment_status" character varying(20) NOT NULL DEFAULT 'waiting',
  "credit_status" character varying(20) NOT NULL DEFAULT 'pending',
  "credit_tx_signature" character varying(128) NULL,
  "credit_error" text NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  "paid_at" timestamptz NULL,
  "credited_at" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "payments_nowpayments_payment_id_key" UNIQUE ("nowpayments_payment_id"),
  CONSTRAINT "chk_credit_status" CHECK ((credit_status)::text = ANY ((ARRAY['pending'::character varying, 'credited'::character varying, 'failed'::character varying])::text[])),
  CONSTRAINT "chk_payment_status" CHECK ((payment_status)::text = ANY ((ARRAY['waiting'::character varying, 'confirming'::character varying, 'confirmed'::character varying, 'sending'::character varying, 'partially_paid'::character varying, 'finished'::character varying, 'failed'::character varying, 'refunded'::character varying, 'expired'::character varying])::text[]))
);
-- Create index "idx_payments_credit_status" to table: "payments"
CREATE INDEX "idx_payments_credit_status" ON "payments" ("credit_status");
-- Create index "idx_payments_invoice_id" to table: "payments"
CREATE INDEX "idx_payments_invoice_id" ON "payments" ("nowpayments_invoice_id");
-- Create index "idx_payments_order_id" to table: "payments"
CREATE INDEX "idx_payments_order_id" ON "payments" ("nowpayments_order_id");
-- Create index "idx_payments_payment_status" to table: "payments"
CREATE INDEX "idx_payments_payment_status" ON "payments" ("payment_status");
-- Create index "idx_payments_wallet_address" to table: "payments"
CREATE INDEX "idx_payments_wallet_address" ON "payments" ("wallet_address");
