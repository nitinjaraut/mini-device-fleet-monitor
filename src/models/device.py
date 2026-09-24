"""
Domain models for the Mini Device Fleet Monitor.

Uses Pydantic v2 for strict runtime validation and serialization.
All models are immutable data containers — business logic lives in the service layer.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request Models (what the client sends)
# ---------------------------------------------------------------------------


class DeviceRegistrationRequest(BaseModel):
    """Payload for POST /devices."""

    id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the device.",
        examples=["device-01"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Human-readable name for the device.",
        examples=["Lab Device 01"],
    )


class HeartbeatRequest(BaseModel):
    """Payload for POST /devices/{id}/heartbeat.

    `timestamp` and `status` are required; any additional fields
    (cpu_usage, signal_strength, etc.) are captured in `extra`.
    """

    timestamp: datetime = Field(
        ...,
        description="ISO-8601 timestamp of the heartbeat.",
        examples=["2026-09-21T10:30:00Z"],
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Device-reported status (e.g. 'OK', 'WARN').",
        examples=["OK"],
    )

    # Capture any additional metrics the device sends.
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Internal Storage Model
# ---------------------------------------------------------------------------


class DeviceRecord:
    """Internal mutable record stored in the repository.

    Not a Pydantic model — intentionally plain Python for performance
    and thread-safe mutation via the repository lock.
    """

    __slots__ = (
        "id",
        "name",
        "registered_at",
        "last_heartbeat",
        "last_status",
        "extra_metrics",
    )

    def __init__(self, device_id: str, name: str) -> None:
        self.id: str = device_id
        self.name: str = name
        self.registered_at: datetime = datetime.now(timezone.utc)
        self.last_heartbeat: Optional[datetime] = None
        self.last_status: Optional[str] = None
        self.extra_metrics: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Response Models (what the API returns)
# ---------------------------------------------------------------------------


class DeviceResponse(BaseModel):
    """Serialized device returned by GET /devices and GET /devices/{id}."""

    id: str
    name: str
    status: str = Field(description="Computed: ONLINE or OFFLINE.")
    last_heartbeat: Optional[datetime] = None
    registered_at: datetime
    last_reported_status: Optional[str] = Field(
        default=None,
        description="The status string the device last reported in its heartbeat.",
    )
    extra_metrics: dict[str, Any] = Field(default_factory=dict)


class FleetSummaryResponse(BaseModel):
    """Serialized fleet summary returned by GET /summary."""

    total: int
    online: int
    offline: int
