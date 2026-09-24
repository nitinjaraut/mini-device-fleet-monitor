"""
Tests for device registration (POST /devices).

Covers:
  - Successful registration
  - Duplicate ID rejection (409)
  - Input validation (missing/empty fields)
  - Multiple device registration
"""

import pytest


class TestDeviceRegistration:
    """Tests for the POST /devices endpoint."""

    def test_register_device_success(self, client):
        """A valid registration should return 201 with the device data."""
        payload = {"id": "device-01", "name": "Lab Device 01"}
        response = client.post("/devices", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "device-01"
        assert data["name"] == "Lab Device 01"
        assert data["status"] == "OFFLINE"  # No heartbeat yet
        assert data["last_heartbeat"] is None
        assert data["registered_at"] is not None

    def test_register_duplicate_device_returns_409(self, client):
        """Registering the same device ID twice should return 409."""
        payload = {"id": "device-01", "name": "Lab Device 01"}
        client.post("/devices", json=payload)

        response = client.post("/devices", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_register_device_missing_id(self, client):
        """Missing 'id' field should return 422 validation error."""
        payload = {"name": "Lab Device 01"}
        response = client.post("/devices", json=payload)
        assert response.status_code == 422

    def test_register_device_missing_name(self, client):
        """Missing 'name' field should return 422 validation error."""
        payload = {"id": "device-01"}
        response = client.post("/devices", json=payload)
        assert response.status_code == 422

    def test_register_device_empty_id(self, client):
        """Empty string for 'id' should return 422 validation error."""
        payload = {"id": "", "name": "Lab Device 01"}
        response = client.post("/devices", json=payload)
        assert response.status_code == 422

    def test_register_device_empty_name(self, client):
        """Empty string for 'name' should return 422 validation error."""
        payload = {"id": "device-01", "name": ""}
        response = client.post("/devices", json=payload)
        assert response.status_code == 422

    def test_register_multiple_devices(self, client):
        """Multiple unique devices should all register successfully."""
        for i in range(1, 4):
            payload = {"id": f"device-{i:02d}", "name": f"Device {i:02d}"}
            response = client.post("/devices", json=payload)
            assert response.status_code == 201

        # Verify all are listed
        response = client.get("/devices")
        assert len(response.json()) == 3

    def test_register_device_empty_body(self, client):
        """Completely empty request body should return 422."""
        response = client.post("/devices", json={})
        assert response.status_code == 422
