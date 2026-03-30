from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health")


@router.get("", response_model=HealthResponse, summary="Health check")
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        version=settings.app_version,
        product=settings.app_name,
    )
