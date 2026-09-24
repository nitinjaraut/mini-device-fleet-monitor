"""
API routes for the Mini Device Fleet Monitor.

Each route is a thin adapter: it validates input via Pydantic,
delegates to the DeviceService, and translates domain exceptions
into proper HTTP status codes.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from src.models.device import (
    DeviceRegistrationRequest,
    DeviceResponse,
    FleetSummaryResponse,
    HeartbeatRequest,
)
from src.services.device_service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter()

# The service instance is set by main.py at startup via `set_service()`.
_service: DeviceService | None = None


def set_service(service: DeviceService) -> None:
    """Inject the DeviceService instance. Called once at application startup."""
    global _service
    _service = service


def _get_service() -> DeviceService:
    """Internal helper to retrieve the injected service."""
    if _service is None:
        raise RuntimeError("DeviceService not initialized.")
    return _service


# ---------------------------------------------------------------------------
# 1. Register a Device
# ---------------------------------------------------------------------------


@router.post(
    "/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new device",
    tags=["Devices"],
)
def register_device(request: DeviceRegistrationRequest) -> DeviceResponse:
    """Register a new device in the fleet.

    Returns 201 on success, 409 if the device ID is already registered.
    """
    try:
        device = _get_service().register_device(request)
        logger.info("Device registered: %s (%s)", request.id, request.name)
        return device
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# 2. Receive a Device Heartbeat
# ---------------------------------------------------------------------------


@router.post(
    "/devices/{device_id}/heartbeat",
    response_model=DeviceResponse,
    summary="Send a heartbeat for a device",
    tags=["Heartbeats"],
)
def receive_heartbeat(
    device_id: str, request: HeartbeatRequest
) -> DeviceResponse:
    """Ingest a heartbeat from a registered device.

    Returns 200 on success, 404 if the device is not registered.
    """
    try:
        device = _get_service().receive_heartbeat(device_id, request)
        logger.debug("Heartbeat received: %s", device_id)
        return device
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# 3. List Devices
# ---------------------------------------------------------------------------


@router.get(
    "/devices",
    response_model=list[DeviceResponse],
    summary="List all registered devices",
    tags=["Devices"],
)
def list_devices() -> list[DeviceResponse]:
    """Return all registered devices with their current computed status."""
    return _get_service().list_devices()


# ---------------------------------------------------------------------------
# 4. Get Device Details
# ---------------------------------------------------------------------------


@router.get(
    "/devices/{device_id}",
    response_model=DeviceResponse,
    summary="Get details for a single device",
    tags=["Devices"],
)
def get_device(device_id: str) -> DeviceResponse:
    """Retrieve details for a specific device by ID.

    Returns 404 if the device is not registered.
    """
    try:
        return _get_service().get_device(device_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# 5. Fleet Summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=FleetSummaryResponse,
    summary="Get fleet summary",
    tags=["Fleet"],
)
def get_fleet_summary() -> FleetSummaryResponse:
    """Return aggregated fleet statistics (total, online, offline)."""
    return _get_service().get_fleet_summary()
