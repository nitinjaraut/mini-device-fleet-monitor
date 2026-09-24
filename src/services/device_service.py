"""
Device service — business logic layer.

Encapsulates all domain rules:
  - Device registration (idempotency guard)
  - Heartbeat ingestion (updating last_heartbeat + metrics)
  - Status computation (ONLINE/OFFLINE based on 30-second timeout)
  - Fleet summary aggregation

The service depends on a DeviceRepository and a configurable timeout,
both injected via the constructor for easy testing.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.config import DEVICE_TIMEOUT_SECONDS
from src.models.device import (
    DeviceRecord,
    DeviceRegistrationRequest,
    DeviceResponse,
    FleetSummaryResponse,
    HeartbeatRequest,
)
from src.repository.device_repository import DeviceRepository


class DeviceService:
    """Core business logic for the fleet monitor."""

    def __init__(
        self,
        repository: Optional[DeviceRepository] = None,
        timeout_seconds: int = DEVICE_TIMEOUT_SECONDS,
    ) -> None:
        self._repo = repository or DeviceRepository()
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_device(self, request: DeviceRegistrationRequest) -> DeviceResponse:
        """Register a new device. Raises ValueError if ID is already taken."""
        record = DeviceRecord(device_id=request.id, name=request.name)
        if not self._repo.add(record):
            raise ValueError(f"Device with id '{request.id}' already exists.")
        return self._to_response(record)

    def receive_heartbeat(
        self, device_id: str, request: HeartbeatRequest
    ) -> DeviceResponse:
        """Process an incoming heartbeat for a registered device.

        Raises LookupError if the device is not registered.
        """
        record = self._repo.get(device_id)
        if record is None:
            raise LookupError(f"Device '{device_id}' not found.")

        # Update mutable fields on the record (under the repo's lock scope
        # since we hold a reference — the dict value is the same object).
        record.last_heartbeat = request.timestamp
        record.last_status = request.status

        # Merge any extra fields the device sent (cpu_usage, signal_strength, etc.)
        if hasattr(request, "model_extra") and request.model_extra:
            record.extra_metrics.update(request.model_extra)

        return self._to_response(record)

    def list_devices(self) -> list[DeviceResponse]:
        """Return all registered devices with their computed status."""
        return [self._to_response(r) for r in self._repo.get_all()]

    def get_device(self, device_id: str) -> DeviceResponse:
        """Return a single device's details. Raises LookupError if not found."""
        record = self._repo.get(device_id)
        if record is None:
            raise LookupError(f"Device '{device_id}' not found.")
        return self._to_response(record)

    def get_fleet_summary(self) -> FleetSummaryResponse:
        """Aggregate fleet-wide online/offline counts."""
        devices = self._repo.get_all()
        now = datetime.now(timezone.utc)
        online = sum(1 for d in devices if self._is_online(d, now))
        return FleetSummaryResponse(
            total=len(devices),
            online=online,
            offline=len(devices) - online,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_online(self, record: DeviceRecord, now: datetime) -> bool:
        """A device is ONLINE iff it sent a heartbeat within the timeout window."""
        if record.last_heartbeat is None:
            return False
        elapsed = (now - record.last_heartbeat).total_seconds()
        return elapsed <= self._timeout_seconds

    def _compute_status(self, record: DeviceRecord) -> str:
        """Return 'ONLINE' or 'OFFLINE' based on the current wall-clock time."""
        now = datetime.now(timezone.utc)
        return "ONLINE" if self._is_online(record, now) else "OFFLINE"

    def _to_response(self, record: DeviceRecord) -> DeviceResponse:
        """Convert an internal DeviceRecord to the public API response model."""
        return DeviceResponse(
            id=record.id,
            name=record.name,
            status=self._compute_status(record),
            last_heartbeat=record.last_heartbeat,
            registered_at=record.registered_at,
            last_reported_status=record.last_status,
            extra_metrics=record.extra_metrics,
        )
