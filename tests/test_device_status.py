"""
Tests for the 30-second ONLINE/OFFLINE timeout behavior.

Uses `freezegun` to mock the system clock so tests run instantly
instead of waiting 30+ real seconds. The freeze_time context manager
is only used around the status-check calls (not around Pydantic
model construction) to avoid schema generation conflicts.

Covers:
  - Device OFFLINE immediately after registration (no heartbeat)
  - Device ONLINE after heartbeat
  - Device transitions to OFFLINE after 30 seconds of silence
  - Device recovers to ONLINE after sending a new heartbeat
  - Boundary: exactly 30 seconds (still ONLINE)
  - Boundary: 31 seconds (OFFLINE)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestDeviceStatus:
    """Tests for the dynamic ONLINE/OFFLINE status computation."""

    def _register_device(self, client, device_id="device-01", name="Lab Device 01"):
        """Helper to register a device."""
        response = client.post("/devices", json={"id": device_id, "name": name})
        assert response.status_code == 201

    def _send_heartbeat(self, client, device_id, timestamp_str):
        """Helper to send a heartbeat with a given timestamp string."""
        response = client.post(
            f"/devices/{device_id}/heartbeat",
            json={"timestamp": timestamp_str, "status": "OK"},
        )
        assert response.status_code == 200
        return response.json()

    def test_device_offline_after_registration(self, client):
        """A newly registered device with no heartbeat should be OFFLINE."""
        self._register_device(client)

        response = client.get("/devices/device-01")
        assert response.json()["status"] == "OFFLINE"

    def test_device_online_after_heartbeat(self, client):
        """Sending a heartbeat at the current time should make device ONLINE."""
        self._register_device(client)

        now = datetime.now(timezone.utc)
        self._send_heartbeat(client, "device-01", now.isoformat())

        response = client.get("/devices/device-01")
        assert response.json()["status"] == "ONLINE"

    def test_device_offline_after_timeout(self, client):
        """If 31 seconds pass without a heartbeat, device should go OFFLINE."""
        self._register_device(client)

        # Send heartbeat at a known time
        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
        self._send_heartbeat(client, "device-01", heartbeat_time.isoformat())

        # Immediately after — ONLINE (mock "now" to be same as heartbeat time)
        check_time = heartbeat_time
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "ONLINE"

        # 31 seconds later — OFFLINE
        check_time_later = heartbeat_time + timedelta(seconds=31)
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time_later
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "OFFLINE"

    def test_device_online_at_exactly_30_seconds(self, client):
        """At exactly 30 seconds since the last heartbeat, device is still ONLINE."""
        self._register_device(client)

        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
        self._send_heartbeat(client, "device-01", heartbeat_time.isoformat())

        # Exactly 30 seconds later — boundary, should still be ONLINE
        check_time = heartbeat_time + timedelta(seconds=30)
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "ONLINE"

    def test_device_offline_at_31_seconds(self, client):
        """At 31 seconds since the last heartbeat, device transitions to OFFLINE."""
        self._register_device(client)

        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
        self._send_heartbeat(client, "device-01", heartbeat_time.isoformat())

        # 31 seconds later — should be OFFLINE
        check_time = heartbeat_time + timedelta(seconds=31)
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "OFFLINE"

    def test_device_recovery_after_new_heartbeat(self, client):
        """An OFFLINE device should recover to ONLINE when a new heartbeat arrives."""
        self._register_device(client)

        # Heartbeat at T=0
        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)
        self._send_heartbeat(client, "device-01", heartbeat_time.isoformat())

        # T=31s → OFFLINE
        check_time = heartbeat_time + timedelta(seconds=31)
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "OFFLINE"

        # New heartbeat at T=35s
        new_heartbeat_time = heartbeat_time + timedelta(seconds=35)
        self._send_heartbeat(client, "device-01", new_heartbeat_time.isoformat())

        # Check status at T=35s → should be ONLINE
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = new_heartbeat_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/devices/device-01")
            assert response.json()["status"] == "ONLINE"

    def test_get_nonexistent_device_returns_404(self, client):
        """Requesting a device that doesn't exist should return 404."""
        response = client.get("/devices/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
