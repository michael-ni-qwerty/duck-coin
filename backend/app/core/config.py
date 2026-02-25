from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Application
    app_name: str = "DuckCoin Presale API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Solana Configuration (for on-chain credit_allocation calls)
    solana_rpc_url: str = "https://api.devnet.solana.com"
    presale_program_id: str = "9GprBhFEyLipafFmS75rta8HGZTU5WPZRG3tWGJDBrmC"
    presale_token_mint: str = ""
    # Admin keypair (Base58 encoded) — signs credit_allocation transactions
    admin_private_key: str = ""
    # Presale start date (ISO format, e.g. "2026-03-01") — day 1 of the tokenomics schedule
    presale_start_date: str = ""

    # NOWPayments Configuration
    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""
    nowpayments_api_url: str = "https://api.nowpayments.io/v1"
    nowpayments_sandbox: bool = False
    # Public base URL used by external providers (e.g. NOWPayments IPN callbacks)
    public_api_base_url: str = ""

    # Invoice anti-abuse guardrails
    invoice_rate_limit_window_seconds: int = 60
    invoice_rate_limit_max_per_window: int = 5
    invoice_max_active_per_wallet: int = 3
    invoice_active_window_hours: int = 24

    # Database (Tortoise ORM format)
    database_url: str = "postgres://user:password@localhost:5432/duckcoin"

    @property
    def cleaned_database_url(self) -> str:
        """Strip problematic query parameters like sslmode from database_url."""
        url = self.database_url
        if "?" in url:
            base, query = url.split("?", 1)
            params = query.split("&")
            # Filter out sslmode and ssl_mode
            filtered_params = [p for p in params if not p.startswith(("sslmode=", "ssl_mode="))]
            if filtered_params:
                return f"{base}?{'&'.join(filtered_params)}"
            return base
        return url

    @property
    def tortoise_config(self) -> dict:
        """Tortoise ORM configuration."""
        return {
            "connections": {
                "default": self.cleaned_database_url,
            },
            "apps": {
                "models": {
                    "models": ["app.models.presale", "aerich.models"],
                    "default_connection": "default",
                },
            },
        }

    # CORS
    cors_origins: str = '["http://localhost:3000","http://localhost:8080"]'

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.cors_origins)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
