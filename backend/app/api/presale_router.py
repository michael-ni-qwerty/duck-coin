from fastapi import APIRouter

from app.api.presale_endpoints.investors import router as investors_router
from app.api.presale_endpoints.onchain import router as onchain_router
from app.api.presale_endpoints.payments import router as payments_router
from app.api.presale_endpoints.nowpayments import router as nowpayments_router

router = APIRouter(prefix="/presale", tags=["presale"])

router.include_router(payments_router)
router.include_router(onchain_router)
router.include_router(investors_router)
router.include_router(nowpayments_router)
