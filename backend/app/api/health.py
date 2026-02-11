from fastapi import APIRouter
from datetime import datetime, timezone

from app.services.solana import solana_service
from app.services.nowpayments import nowpayments_client

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", summary="Readiness check")
async def readiness_check():
    """Readiness check — verifies Solana RPC and NOWPayments API are reachable."""
    checks = {}

    # Check Solana RPC
    try:
        checks["solana_rpc"] = await solana_service.is_connected()
    except Exception:
        checks["solana_rpc"] = False

    # Check NOWPayments API
    try:
        status_resp = await nowpayments_client.get_status()
        checks["nowpayments"] = status_resp.get("message") == "OK"
    except Exception:
        checks["nowpayments"] = False

    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
