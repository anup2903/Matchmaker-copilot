from fastapi import APIRouter

from app.api import candidates, clients, feedback, mirror, profile_check

api_router = APIRouter(prefix="/api")
for module in (clients, candidates, profile_check, feedback, mirror):
    api_router.include_router(module.router)
