from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.essays import router as essays_router
from app.api.routes.health import router as health_router
from app.api.routes.materials import router as materials_router
from app.api.routes.providers import router as providers_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.training import router as training_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(health_router)
api_router.include_router(providers_router)
api_router.include_router(essays_router, prefix="/essays")
api_router.include_router(reviews_router, prefix="/essays")
api_router.include_router(training_router, prefix="/training")
api_router.include_router(materials_router, prefix="/materials")
