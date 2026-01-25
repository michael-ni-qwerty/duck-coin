from fastapi import APIRouter
from datetime import datetime

from app.blockchain import blockchain_registry, BlockchainType

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "supported_chains": [c.value for c in blockchain_registry.get_supported_chains()],
    }


@router.get("/ready", summary="Readiness check")
async def readiness_check():
    """
    Readiness check - verifies all dependencies are available.
    
    Checks connectivity for all registered blockchains.
    """
    checks = {}
    
    # Check each registered blockchain
    for chain_type in blockchain_registry.get_supported_chains():
        try:
            blockchain_service = blockchain_registry.get_blockchain_service(chain_type)
            is_connected = await blockchain_service.is_connected()
            checks[f"{chain_type.value}_rpc"] = is_connected
        except Exception:
            checks[f"{chain_type.value}_rpc"] = False
    
    # Check Redis via Solana nonce service (shared across chains)
    try:
        if blockchain_registry.is_registered(BlockchainType.SOLANA):
            nonce_service = blockchain_registry.get_nonce_service(BlockchainType.SOLANA)
            redis = await nonce_service._get_redis()
            await redis.ping()
            checks["redis"] = True
    except Exception:
        checks["redis"] = False
    
    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }
