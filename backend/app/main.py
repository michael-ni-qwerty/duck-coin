from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings
from app.api import presale, health
from app.blockchain.registry import blockchain_registry, register_chains


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup - register all blockchain implementations
    register_chains()
    yield
    # Shutdown - cleanup all blockchain connections
    await blockchain_registry.disconnect_all()


app = FastAPI(
    title=settings.app_name,
    description="""
    DuckCoin Presale API - Multi-Chain Support
    
    This API provides endpoints for:
    - Generating signed purchase authorizations (multi-chain)
    - Querying vesting information
    - Getting presale configuration and statistics
    
    ## Supported Blockchains
    
    - **Solana**: ed25519 signatures via ed25519_program
    - **Ethereum** (coming soon): EIP-712 typed data signatures
    - **Tron** (coming soon): secp256k1 signatures
    
    ## Authentication Flow
    
    1. Client requests purchase authorization via `/api/v1/presale/authorize-purchase`
    2. Backend generates unique nonce and signs the authorization
    3. Client builds chain-specific transaction with signature verification
    4. Client submits transaction to the blockchain
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(presale.router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": f"{settings.api_v1_prefix}/presale",
    }


# Register Tortoise ORM with FastAPI
register_tortoise(
    app,
    config=settings.tortoise_config,
    generate_schemas=False,  # Use Atlas for migrations
    add_exception_handlers=True,
)
