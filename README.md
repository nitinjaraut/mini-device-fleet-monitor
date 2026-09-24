# Mini Device Fleet Monitor

A lightweight backend service that monitors a fleet of simulated IoT devices. Each device periodically sends a **heartbeat**; the application tracks them and dynamically reports each device as **ONLINE** or **OFFLINE** based on a configurable timeout (default: 30 seconds).

---

## Design / Architecture

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   Simulator  │──────▶│   API Layer   │──────▶│  Service Layer   │──────▶│    Repository     │
│  (aiohttp)   │  HTTP │  (FastAPI)    │       │  (Business Logic)│       │ (In-Memory Store) │
└──────────────┘       └───────────────┘       └──────────────────┘       └──────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │  Dashboard   │
                       │ (Static HTML)│
                       └──────────────┘
```

**Layered architecture** with clear separation of concerns:

| Layer | Responsibility | Files |
|-------|---------------|-------|
| **Models** | Pydantic request/response schemas + internal record | `src/models/device.py` |
| **Repository** | Thread-safe in-memory CRUD operations | `src/repository/device_repository.py` |
| **Service** | Business logic: registration, heartbeat, status computation | `src/services/device_service.py` |
| **API** | HTTP routing, input validation, error translation | `src/api/routes.py` |
| **Config** | Environment-variable-driven configuration | `src/config.py` |

### Key Design Decisions

1. **Dynamic status computation**: Device status (`ONLINE`/`OFFLINE`) is computed on every API call as `(now - last_heartbeat) <= timeout`. No background timers, no stale caches, no clock drift.
2. **Thread safety**: The repository uses a `threading.Lock` to protect concurrent access — correct for Python's GIL + uvicorn worker model.
3. **Dependency injection**: The service accepts a repository and timeout via constructor, making unit testing trivial.
4. **Extra metrics via `extra="allow"`**: Heartbeats can include arbitrary additional fields (e.g. `cpu_usage`, `signal_strength`) without schema changes.

---

## Prerequisites

- **Python 3.11+**
- **pip** (or **Docker** for containerized execution)

---

## How to Build the Application

```bash
# Clone the repository
git clone <repo-url>
cd <project-directory>

# Create a virtual environment
python -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## How to Run the Application

```bash
# Start the server (default: http://localhost:8000)
python -m src.main
```

The server will start on `http://localhost:8000`. You can also configure via environment variables:

```bash
PORT=9000 DEVICE_TIMEOUT_SECONDS=60 python -m src.main
```

### With Docker

```bash
# One command to start both server and simulator
docker compose up --build
```

### Interactive API Documentation

Once the server is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## How to Run the Simulator

In a **separate terminal** (while the server is running):

```bash
python -m simulator.simulator
```

### Simulator Controls

| Key | Action |
|-----|--------|
| `1`–`5` | Toggle `device-01` through `device-05` on/off |
| `q` | Quit the simulator |

**To observe the OFFLINE transition**: Press a number key (e.g., `3`) to pause `device-03`. Wait 30+ seconds, then query the devices endpoint or check the dashboard to see it transition to OFFLINE.

---

## How to Run the Tests

```bash
# Run all tests with verbose output
pytest -v

# Run specific test files
pytest tests/test_device_registration.py -v
pytest tests/test_device_status.py -v

# Run with coverage report
pytest --cov=src --cov-report=term-missing -v
```

---

## Example API Requests

### 1. Register a Device

```bash
curl -X POST http://localhost:8000/devices \
  -H "Content-Type: application/json" \
  -d '{"id": "device-01", "name": "Lab Device 01"}'
```

### 2. Send a Heartbeat

```bash
curl -X POST http://localhost:8000/devices/device-01/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"timestamp": "2026-09-21T10:30:00Z", "status": "OK", "cpu_usage": 42, "signal_strength": -71}'
```

### 3. List All Devices

```bash
curl http://localhost:8000/devices
```

### 4. Get Device Details

```bash
curl http://localhost:8000/devices/device-01
```

### 5. Fleet Summary

```bash
curl http://localhost:8000/summary
```

---

## Assumptions

1. **In-memory storage is acceptable** — data is lost on server restart. The repository interface allows easy migration to a persistent store.
2. **Device IDs are unique strings** — enforced at registration time (409 Conflict on duplicates).
3. **Heartbeat timestamps are trusted** — the server uses the timestamp provided by the device for display, but computes ONLINE/OFFLINE status based on server wall-clock time at the moment the heartbeat is received.
4. **Single-process deployment** — the `threading.Lock` is sufficient for uvicorn's default single-worker mode. For multi-worker, a shared store (Redis/DB) would be needed.
5. **No authentication** — this is an internal monitoring service for a simulated fleet.

---

## Known Limitations

1. **No persistent storage** — all device data is lost on server restart.
2. **Single-worker only** — the in-memory store is per-process; running multiple uvicorn workers would create independent, inconsistent stores.
3. **No pagination** — `GET /devices` returns all devices in a single response. Fine for a small fleet, but would need pagination for thousands of devices.
4. **No rate limiting** — a misbehaving device could flood the heartbeat endpoint.
5. **No WebSocket for real-time dashboard** — the dashboard polls every 2 seconds via HTTP; WebSocket push would be more efficient.

---

## What I Would Improve with One Additional Day

1. **SQLite/PostgreSQL backend** — swap the in-memory repository for a persistent database using SQLAlchemy or Tortoise ORM, with the same repository interface.
2. **WebSocket-powered dashboard** — replace HTTP polling with WebSocket for instant status updates and lower server load.
3. **Structured logging with correlation IDs** — use `structlog` for JSON-formatted logs with per-request trace IDs.
4. **Prometheus metrics endpoint** — expose `/metrics` for fleet health monitoring in Grafana.
5. **Filtering & pagination** — add query parameters to `GET /devices` (e.g., `?status=OFFLINE&page=1&limit=20`).
6. **Graceful shutdown** — drain in-flight requests and cleanly close connections on SIGTERM.
7. **CI/CD pipeline** — GitHub Actions workflow for linting, testing, and building the Docker image.

---

## AI Usage

In accordance with the project guidelines, here is a transparent disclosure of AI assistance utilized during development:

### 1. Which AI tools did you use (if any)?
- **Google Gemini (Antigravity IDE)** with Claude reasoning models for pair-programming and architecture planning.

### 2. What did you use them for?
- Scaffolding the layered directory structure (`models`, `repository`, `services`, `api`).
- Generating boilerplate Pydantic schemas and initial FastAPI route handlers.
- Generating comprehensive test cases (especially setting up `freezegun` fixtures for time mocking).
- Drafting initial sections of documentation.

### 3. What code or suggestions did you reject, change, or improve?
- **Thread Safety Model**: An initial AI proposal suggested using `asyncio.Lock` inside the in-memory repository. Since FastAPI routes in this setup run synchronous database/repository methods in a thread pool (`threadpool`), `asyncio.Lock` would not have guaranteed thread-safety across OS threads. This was rejected and replaced with a Python `threading.Lock` to guarantee true thread safety across concurrent requests.
- **Pydantic Validation**: Strengthened field validation constraints (`min_length=1`, whitespace stripping, and ISO-8601 timestamp parsing with timezone enforcement).
- **Interactive Simulator**: The initial simulator was a simple continuous sleep loop. Enhanced it into an interactive operator console with non-blocking keyboard listeners (`1`–`5` to simulate individual device failure/recovery and `q` to quit).

### 4. How did you personally verify the results?
- **Test Suite**: Executed `python -m pytest -v`, verifying all 28 automated unit and integration tests pass cleanly in ~0.2s.
- **Manual API Testing**: Sent manual `curl` requests to all 5 endpoints (`/devices`, `/devices/{id}/heartbeat`, `/devices/{id}`, `/devices`, `/summary`), confirming status codes, payload shapes, and error handling (404, 409, 422).
- **Timeout Transition Verification**: Paused `device-03` via the simulator keyboard control and verified using both `curl` and the web dashboard that it transitioned to `OFFLINE` precisely after the 30-second window elapsed, and immediately returned to `ONLINE` once resumed.
- **Docker Verification**: Tested containerized build and execution via `docker compose up --build`.
