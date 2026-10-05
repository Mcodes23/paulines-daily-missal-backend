from fastapi import APIRouter

# Import all route modules here
from fastapi_api.api.v1.readings.readings import router as readings_router
from fastapi_api.api.v1.auth.auth import router as auth_router
from fastapi_api.api.v1.auth.profile import router as profile_router
from fastapi_api.api.v1.subscriptions.subscriptions import router as subscriptions_router

# ───────────────────────────────────────────────
# Aggregate versioned routers
# ───────────────────────────────────────────────
api_router = APIRouter(prefix="/v1")

# Attach each feature router
api_router.include_router(readings_router, prefix="/readings", tags=["Readings"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(profile_router, prefix="/auth", tags=["Profile"])
api_router.include_router(subscriptions_router, prefix="/subscriptions", tags=["Subscriptions"])
