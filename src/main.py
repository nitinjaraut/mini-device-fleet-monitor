"""
Mini Device Fleet Monitor — Application Entry Point.

Creates the FastAPI application, wires up the service layer,
mounts the static dashboard, and starts the Uvicorn server.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router, set_service
from src.config import HOST, PORT
from src.repository.device_repository import DeviceRepository
from src.services.device_service import DeviceService

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fleet-monitor")

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    app = FastAPI(
        title="Mini Device Fleet Monitor",
        description=(
            "A lightweight service that monitors a fleet of simulated devices. "
            "Each device sends periodic heartbeats; the application tracks them "
            "and reports ONLINE/OFFLINE status based on a configurable timeout."
        ),
        version="1.0.0",
    )

    # Wire up the service layer
    repository = DeviceRepository()
    service = DeviceService(repository=repository)
    set_service(service)

    # Mount API routes
    app.include_router(router)

    # Serve the static dashboard (if the static/ directory exists)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def serve_dashboard():
            """Serve the single-page dashboard."""
            return FileResponse(str(static_dir / "index.html"))

    logger.info("Fleet Monitor application initialized.")
    return app


# Create the app instance (used by uvicorn)
app = create_app()

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server on %s:%d", HOST, PORT)
    uvicorn.run(
        "src.main:app",
        host=HOST,
        port=PORT,
        reload=bool(os.getenv("RELOAD", "")),
        log_level="info",
    )
