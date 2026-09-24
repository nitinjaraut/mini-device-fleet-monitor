"""
In-memory device repository.

Thread-safe storage layer using a threading.Lock to protect concurrent
read/write access. All data access goes through this single class,
making it trivial to swap in a database backend later.
"""

import threading
from typing import Optional

from src.models.device import DeviceRecord


class DeviceRepository:
    """Thread-safe in-memory store for device records."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceRecord] = {}
        self._lock: threading.Lock = threading.Lock()

    def add(self, record: DeviceRecord) -> bool:
        """Add a new device. Returns False if the ID already exists."""
        with self._lock:
            if record.id in self._devices:
                return False
            self._devices[record.id] = record
            return True

    def get(self, device_id: str) -> Optional[DeviceRecord]:
        """Retrieve a single device by ID. Returns None if not found."""
        with self._lock:
            return self._devices.get(device_id)

    def get_all(self) -> list[DeviceRecord]:
        """Return a snapshot list of all registered devices."""
        with self._lock:
            return list(self._devices.values())

    def exists(self, device_id: str) -> bool:
        """Check whether a device ID is registered."""
        with self._lock:
            return device_id in self._devices

    def count(self) -> int:
        """Return the total number of registered devices."""
        with self._lock:
            return len(self._devices)

    def clear(self) -> None:
        """Remove all devices. Useful for test teardown."""
        with self._lock:
            self._devices.clear()
