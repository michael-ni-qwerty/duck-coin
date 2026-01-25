from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Application
    app_name: str = "DuckCoin Presale API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    
    # Solana Configuration
    solana_rpc_url: str = "https://api.devnet.solana.com"
    presale_program_id: str = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"
    
    # Token Mints
    presale_token_mint: str = ""
    usdt_mint: str = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    usdc_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    # Treasury
    treasury_wallet: str = ""
    
    # Authorized Signer (Base58 encoded private key)
    authorized_signer_private_key: str = ""
    
    # Database (Tortoise ORM format)
    database_url: str = "postgres://user:password@localhost:5432/duckcoin"
    
    @property
    def tortoise_config(self) -> dict:
        """Tortoise ORM configuration."""
        return {
            "connections": {
                "default": self.database_url,
            },
            "apps": {
                "models": {
                    "models": ["app.models.presale", "aerich.models"],
                    "default_connection": "default",
                },
            },
        }
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT Settings
    jwt_secret_key: str = "your-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
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
