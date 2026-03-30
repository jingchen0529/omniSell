from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import initialize_database
from app.tasks.queue import build_worker_id, run_project_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    settings = get_settings()
    stop_event: Event | None = None
    worker_thread: Thread | None = None

    if settings.run_embedded_project_worker:
        stop_event = Event()
        worker_thread = Thread(
            target=run_project_worker,
            kwargs={
                "worker_id": f"embedded:{build_worker_id()}",
                "poll_interval": settings.project_job_poll_interval_seconds,
                "stop_event": stop_event,
            },
            daemon=True,
            name="omnisell-project-worker",
        )
        worker_thread.start()

    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if worker_thread is not None:
            worker_thread.join(timeout=max(settings.project_job_poll_interval_seconds * 2, 1))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    settings.uploads_root.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.uploads_root), name="uploads")

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", summary="Root endpoint")
    def read_root() -> dict[str, str]:
        current_settings = get_settings()
        return {
            "name": current_settings.app_name,
            "message": "OmniSell backend is running.",
            "docs": "/docs",
        }

    return app


app = create_app()
