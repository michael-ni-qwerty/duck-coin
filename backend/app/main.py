import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.core.config import settings
from app.api import health, presale_router
from app.services.solana import solana_service
from app.workers.daily_config import daily_config_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Start background workers
    worker_task = asyncio.create_task(daily_config_loop())
    logger.info("Started daily config update worker")
    yield
    # Shutdown - cancel worker and close connections
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await solana_service.close()


app = FastAPI(
    title=settings.app_name,
    description="""
    DuckCoin Presale API — NOWPayments Integration

    This API provides endpoints for:
    - Creating payment invoices via NOWPayments (any crypto)
    - Receiving IPN webhooks and crediting on-chain allocations
    - Querying payment status and on-chain allocation data
    - Getting presale configuration and statistics

    ## Payment Flow

    1. Frontend calls `POST /api/v1/presale/create-invoice` with wallet + USD amount
    2. User is redirected to NOWPayments hosted page to pay with any crypto
    3. NOWPayments sends IPN webhook to `POST /api/v1/presale/ipn-webhook`
    4. Backend verifies payment and calls `credit_allocation` on the Solana program
    5. User's token allocation is recorded on-chain
    """,
    version="2.0.0",
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
app.include_router(presale_router.router, prefix=settings.api_v1_prefix)


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
