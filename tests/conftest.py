"""
Shared test fixtures for the Mini Device Fleet Monitor.

Provides a fresh FastAPI TestClient and DeviceService for each test,
ensuring complete isolation between test cases.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.routes import set_service
from src.main import create_app
from src.repository.device_repository import DeviceRepository
from src.services.device_service import DeviceService


@pytest.fixture()
def repository():
    """Provide a fresh in-memory repository for each test."""
    return DeviceRepository()


@pytest.fixture()
def service(repository):
    """Provide a fresh DeviceService backed by the test repository."""
    return DeviceService(repository=repository)


@pytest.fixture()
def client(service):
    """Provide a TestClient with a cleanly injected service."""
    app = create_app()
    # Override the global service with our test-specific instance
    set_service(service)
    with TestClient(app) as c:
        yield c
