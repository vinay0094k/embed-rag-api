from fastapi import APIRouter

from app.api.v1.endpoints import auth, collections, documents, search, uploads, health, system

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(collections.router)
router.include_router(documents.router)
router.include_router(search.router)
router.include_router(uploads.router)
router.include_router(health.router)
router.include_router(system.router)
