"""
Tests for heartbeat ingestion (POST /devices/{id}/heartbeat).

Covers:
  - Successful heartbeat recording
  - Heartbeat for non-existent device (404)
  - Heartbeat with additional metrics (cpu_usage, signal_strength)
  - Heartbeat updates device status to ONLINE
  - Input validation (missing fields)
"""

from datetime import datetime, timezone


class TestHeartbeat:
    """Tests for the POST /devices/{id}/heartbeat endpoint."""

    def _register_device(self, client, device_id="device-01", name="Lab Device 01"):
        """Helper to register a device before sending heartbeats."""
        response = client.post("/devices", json={"id": device_id, "name": name})
        assert response.status_code == 201
        return response.json()

    def test_heartbeat_success(self, client):
        """A valid heartbeat should return 200 and update the device."""
        self._register_device(client)

        now = datetime.now(timezone.utc).isoformat()
        payload = {"timestamp": now, "status": "OK"}
        response = client.post("/devices/device-01/heartbeat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "device-01"
        assert data["status"] == "ONLINE"
        assert data["last_heartbeat"] is not None
        assert data["last_reported_status"] == "OK"

    def test_heartbeat_nonexistent_device_returns_404(self, client):
        """Sending a heartbeat for an unregistered device should return 404."""
        now = datetime.now(timezone.utc).isoformat()
        payload = {"timestamp": now, "status": "OK"}
        response = client.post("/devices/nonexistent/heartbeat", json=payload)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_heartbeat_with_extra_metrics(self, client):
        """Additional metrics (cpu_usage, signal_strength) should be captured."""
        self._register_device(client)

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "timestamp": now,
            "status": "OK",
            "cpu_usage": 42,
            "signal_strength": -71,
        }
        response = client.post("/devices/device-01/heartbeat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["extra_metrics"]["cpu_usage"] == 42
        assert data["extra_metrics"]["signal_strength"] == -71

    def test_heartbeat_updates_status_to_online(self, client):
        """After registration (OFFLINE), a heartbeat should flip status to ONLINE."""
        self._register_device(client)

        # Before heartbeat — should be OFFLINE
        response = client.get("/devices/device-01")
        assert response.json()["status"] == "OFFLINE"

        # Send heartbeat
        now = datetime.now(timezone.utc).isoformat()
        client.post(
            "/devices/device-01/heartbeat",
            json={"timestamp": now, "status": "OK"},
        )

        # After heartbeat — should be ONLINE
        response = client.get("/devices/device-01")
        assert response.json()["status"] == "ONLINE"

    def test_heartbeat_missing_timestamp(self, client):
        """Missing 'timestamp' should return 422."""
        self._register_device(client)
        response = client.post(
            "/devices/device-01/heartbeat", json={"status": "OK"}
        )
        assert response.status_code == 422

    def test_heartbeat_missing_status(self, client):
        """Missing 'status' should return 422."""
        self._register_device(client)
        now = datetime.now(timezone.utc).isoformat()
        response = client.post(
            "/devices/device-01/heartbeat", json={"timestamp": now}
        )
        assert response.status_code == 422

    def test_heartbeat_invalid_timestamp_format(self, client):
        """An unparseable timestamp should return 422."""
        self._register_device(client)
        response = client.post(
            "/devices/device-01/heartbeat",
            json={"timestamp": "not-a-date", "status": "OK"},
        )
        assert response.status_code == 422

    def test_multiple_heartbeats_update_latest(self, client):
        """The latest heartbeat should overwrite the previous one."""
        self._register_device(client)

        ts1 = "2026-09-21T10:00:00Z"
        ts2 = "2026-09-21T10:05:00Z"

        client.post(
            "/devices/device-01/heartbeat",
            json={"timestamp": ts1, "status": "OK"},
        )
        client.post(
            "/devices/device-01/heartbeat",
            json={"timestamp": ts2, "status": "WARN"},
        )

        response = client.get("/devices/device-01")
        data = response.json()
        assert data["last_reported_status"] == "WARN"
        # The last_heartbeat should reflect the second heartbeat
        assert "10:05:00" in data["last_heartbeat"]
