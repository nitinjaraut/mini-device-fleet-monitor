"""
Tests for fleet summary (GET /summary).

Uses unittest.mock.patch to mock datetime.now in the service layer
for deterministic timeout testing.

Covers:
  - Empty fleet summary
  - All devices ONLINE
  - Mixed ONLINE/OFFLINE
  - All devices OFFLINE (after timeout)
  - Devices that were never heartbeated
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestFleetSummary:
    """Tests for the GET /summary endpoint."""

    def _register_device(self, client, device_id, name):
        """Helper to register a device."""
        response = client.post("/devices", json={"id": device_id, "name": name})
        assert response.status_code == 201

    def _send_heartbeat(self, client, device_id, timestamp_str):
        """Helper to send a heartbeat."""
        response = client.post(
            f"/devices/{device_id}/heartbeat",
            json={"timestamp": timestamp_str, "status": "OK"},
        )
        assert response.status_code == 200

    def test_empty_fleet_summary(self, client):
        """With no devices registered, summary should be all zeros."""
        response = client.get("/summary")
        assert response.status_code == 200
        data = response.json()
        assert data == {"total": 0, "online": 0, "offline": 0}

    def test_all_devices_online(self, client):
        """All devices with recent heartbeats should be ONLINE."""
        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(1, 4):
            self._register_device(client, f"device-{i:02d}", f"Device {i:02d}")
            self._send_heartbeat(
                client, f"device-{i:02d}", heartbeat_time.isoformat()
            )

        # Check summary at the same time as heartbeats
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = heartbeat_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/summary")
            data = response.json()
            assert data == {"total": 3, "online": 3, "offline": 0}

    def test_mixed_online_offline(self, client):
        """Devices with stale heartbeats should be counted as OFFLINE."""
        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)

        # Register 3 devices and send heartbeats at T=0
        for i in range(1, 4):
            self._register_device(client, f"device-{i:02d}", f"Device {i:02d}")
            self._send_heartbeat(
                client, f"device-{i:02d}", heartbeat_time.isoformat()
            )

        # At T=31s, only device-01 sends a fresh heartbeat
        new_time = heartbeat_time + timedelta(seconds=31)
        self._send_heartbeat(client, "device-01", new_time.isoformat())

        # Check summary at T=31s
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = new_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/summary")
            data = response.json()
            assert data["total"] == 3
            assert data["online"] == 1
            assert data["offline"] == 2

    def test_all_devices_offline_after_timeout(self, client):
        """All devices should be OFFLINE if no heartbeats within 30 seconds."""
        heartbeat_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(1, 4):
            self._register_device(client, f"device-{i:02d}", f"Device {i:02d}")
            self._send_heartbeat(
                client, f"device-{i:02d}", heartbeat_time.isoformat()
            )

        # At T=60s, all should be OFFLINE
        check_time = heartbeat_time + timedelta(seconds=60)
        with patch("src.services.device_service.datetime") as mock_dt:
            mock_dt.now.return_value = check_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            response = client.get("/summary")
            data = response.json()
            assert data == {"total": 3, "online": 0, "offline": 3}

    def test_summary_with_devices_never_heartbeated(self, client):
        """Devices registered but never heartbeated should be OFFLINE."""
        self._register_device(client, "device-01", "Device 01")
        self._register_device(client, "device-02", "Device 02")

        response = client.get("/summary")
        data = response.json()
        assert data == {"total": 2, "online": 0, "offline": 2}
