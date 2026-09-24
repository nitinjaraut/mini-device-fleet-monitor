"""
Mini Device Fleet Monitor — Application Entry Point.

Creates the FastAPI application, wires up the service layer,
mounts the static dashboard, and starts the Uvicorn server.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse
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
        docs_url=None,    # Disable default so we can serve a custom one with navigation
        redoc_url=None,   # Disable ReDoc
    )

    # Custom /docs page with a "← Back to Dashboard" navigation bar
    @app.get("/docs", include_in_schema=False)
    def custom_swagger_ui():
        swagger_page = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " — API Docs",
        )
        # Inject a slim navigation bar above the Swagger UI
        nav_bar = """
        <div style="
            position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
            background: linear-gradient(135deg, #1a1d27, #222632);
            padding: 10px 24px;
            display: flex; align-items: center; gap: 16px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            font-family: 'Inter', -apple-system, sans-serif;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3);
        ">
            <a href="/" style="
                color: #60a5fa; text-decoration: none; font-size: 14px;
                font-weight: 500; display: flex; align-items: center; gap: 6px;
                background: rgba(96,165,250,0.1); padding: 6px 14px;
                border-radius: 20px; border: 1px solid rgba(96,165,250,0.2);
                transition: all 0.2s;
            " onmouseover="this.style.background='rgba(96,165,250,0.2)';this.style.borderColor='#60a5fa'"
              onmouseout="this.style.background='rgba(96,165,250,0.1)';this.style.borderColor='rgba(96,165,250,0.2)'">
                ← Back to Dashboard
            </a>
            <span style="color: #9aa0ab; font-size: 13px;">
                ⚡ Mini Device Fleet Monitor — Interactive API Documentation
            </span>
        </div>
        <style>body { padding-top: 48px !important; }</style>
        """
        # Inject the nav bar right after <body>
        modified_html = swagger_page.body.decode().replace("<body>", "<body>" + nav_bar)
        return HTMLResponse(content=modified_html)


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
