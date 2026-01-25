# Domain separator for signature verification (must match smart contract)
DOMAIN_SEPARATOR = b"PRESALE_V1"

# Payment type identifiers (must match smart contract)
PAYMENT_SOL = 0
PAYMENT_USDT = 1
PAYMENT_USDC = 2

# PDA Seeds (must match smart contract)
CONFIG_SEED = b"config"
VESTING_SEED = b"vesting"
NONCE_SEED = b"nonce"
VAULT_SEED = b"vault"

# Signature message size
SIGNATURE_MESSAGE_SIZE = 131
