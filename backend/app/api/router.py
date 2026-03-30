from fastapi import APIRouter

from app.api.routes import auth, health, projects, system_settings

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(system_settings.router, tags=["system-settings"])
