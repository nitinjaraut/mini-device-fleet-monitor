"""
Device Fleet Simulator — Interactive CLI.

Simulates 5 devices sending heartbeats every 5 seconds to the fleet
monitor server. Provides interactive keyboard controls to toggle
individual devices on/off, allowing observation of the 30-second
ONLINE → OFFLINE timeout transition.

Usage:
    python -m simulator.simulator [--server-url http://localhost:8000]

Controls:
    1-5     Toggle device-01 through device-05 on/off
    q       Quit the simulator
"""

import argparse
import asyncio
import random
import signal
import sys
import time
from datetime import datetime, timezone

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp is required. Install it with: pip install aiohttp")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SERVER_URL = "http://localhost:8000"
HEARTBEAT_INTERVAL = 5  # seconds
NUM_DEVICES = 5

# ANSI color codes for terminal output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "dim": "\033[2m",
    "blue": "\033[94m",
}


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


# ---------------------------------------------------------------------------
# Device Simulator
# ---------------------------------------------------------------------------


class SimulatedDevice:
    """Represents a single simulated device."""

    def __init__(self, device_id: str, name: str):
        self.device_id = device_id
        self.name = name
        self.active = True  # Whether this device is sending heartbeats
        self.heartbeat_count = 0
        self.last_error: str | None = None


async def register_device(
    session: aiohttp.ClientSession, server_url: str, device: SimulatedDevice
) -> bool:
    """Register a device with the fleet monitor server."""
    url = f"{server_url}/devices"
    payload = {"id": device.device_id, "name": device.name}
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 201:
                print(
                    f"  {colorize('✓', 'green')} Registered {colorize(device.device_id, 'cyan')} "
                    f"({device.name})"
                )
                return True
            elif resp.status == 409:
                print(
                    f"  {colorize('~', 'yellow')} {colorize(device.device_id, 'cyan')} "
                    f"already registered (resuming)"
                )
                return True
            else:
                body = await resp.text()
                print(
                    f"  {colorize('✗', 'red')} Failed to register {device.device_id}: "
                    f"{resp.status} {body}"
                )
                return False
    except aiohttp.ClientError as e:
        print(f"  {colorize('✗', 'red')} Connection error registering {device.device_id}: {e}")
        return False


async def send_heartbeat(
    session: aiohttp.ClientSession, server_url: str, device: SimulatedDevice
) -> None:
    """Send a single heartbeat for a device."""
    url = f"{server_url}/devices/{device.device_id}/heartbeat"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "cpu_usage": random.randint(5, 95),
        "signal_strength": random.randint(-90, -30),
    }
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                device.heartbeat_count += 1
                device.last_error = None
            else:
                body = await resp.text()
                device.last_error = f"HTTP {resp.status}: {body}"
    except aiohttp.ClientError as e:
        device.last_error = str(e)


def print_status_table(devices: list[SimulatedDevice]) -> None:
    """Print a compact status table for all simulated devices."""
    print()
    print(
        f"  {colorize('Device', 'bold'):>30}  "
        f"{colorize('Active', 'bold'):>20}  "
        f"{colorize('Heartbeats', 'bold'):>20}  "
        f"{colorize('Last Error', 'bold')}"
    )
    print(f"  {'─' * 75}")
    for d in devices:
        active_str = (
            colorize("● SENDING", "green") if d.active else colorize("○ PAUSED", "red")
        )
        error_str = colorize(d.last_error, "red") if d.last_error else colorize("—", "dim")
        print(
            f"  {colorize(d.device_id, 'cyan'):>30}  "
            f"{active_str:>20}  "
            f"{str(d.heartbeat_count):>10}  "
            f"{error_str}"
        )
    print()


async def heartbeat_loop(
    session: aiohttp.ClientSession,
    server_url: str,
    devices: list[SimulatedDevice],
    stop_event: asyncio.Event,
) -> None:
    """Main loop: send heartbeats for all active devices every HEARTBEAT_INTERVAL seconds."""
    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        active_devices = [d for d in devices if d.active]
        paused_devices = [d for d in devices if not d.active]

        # Send heartbeats concurrently for all active devices
        if active_devices:
            tasks = [send_heartbeat(session, server_url, d) for d in active_devices]
            await asyncio.gather(*tasks)

        # Print status
        active_ids = ", ".join(colorize(d.device_id, "green") for d in active_devices)
        paused_ids = ", ".join(colorize(d.device_id, "red") for d in paused_devices) or "none"
        print(
            f"  [{colorize(timestamp, 'dim')}] "
            f"Cycle {cycle}: sent {len(active_devices)} heartbeat(s)  |  "
            f"Paused: {paused_ids}"
        )

        # Wait for the next cycle or stop signal
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def input_listener(
    devices: list[SimulatedDevice], stop_event: asyncio.Event
) -> None:
    """Listen for keyboard input to toggle devices or quit."""
    loop = asyncio.get_event_loop()
    while not stop_event.is_set():
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            line = line.strip().lower()
        except (EOFError, OSError):
            break

        if line == "q":
            print(f"\n  {colorize('Shutting down simulator...', 'yellow')}")
            stop_event.set()
            break

        if line in [str(i) for i in range(1, NUM_DEVICES + 1)]:
            idx = int(line) - 1
            device = devices[idx]
            device.active = not device.active
            state = (
                colorize("RESUMED (sending heartbeats)", "green")
                if device.active
                else colorize("PAUSED (will go OFFLINE after 30s)", "red")
            )
            print(f"\n  → {colorize(device.device_id, 'cyan')}: {state}\n")


async def main(server_url: str) -> None:
    """Main entry point for the simulator."""
    print()
    print(f"  {colorize('╔══════════════════════════════════════════════╗', 'blue')}")
    print(f"  {colorize('║', 'blue')}   {colorize('Mini Device Fleet Simulator', 'bold')}            {colorize('║', 'blue')}")
    print(f"  {colorize('╚══════════════════════════════════════════════╝', 'blue')}")
    print()
    print(f"  Server: {colorize(server_url, 'cyan')}")
    print(f"  Devices: {colorize(str(NUM_DEVICES), 'bold')}")
    print(f"  Heartbeat interval: {colorize(f'{HEARTBEAT_INTERVAL}s', 'bold')}")
    print()

    # Create devices
    devices = [
        SimulatedDevice(
            device_id=f"device-{i:02d}",
            name=f"Lab Device {i:02d}",
        )
        for i in range(1, NUM_DEVICES + 1)
    ]

    stop_event = asyncio.Event()

    # Handle Ctrl+C gracefully
    def handle_signal(*_):
        print(f"\n  {colorize('Received interrupt, shutting down...', 'yellow')}")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    async with aiohttp.ClientSession() as session:
        # Step 1: Register all devices
        print(f"  {colorize('Registering devices...', 'bold')}")
        for device in devices:
            success = await register_device(session, server_url, device)
            if not success:
                print(
                    f"\n  {colorize('ERROR:', 'red')} Could not register {device.device_id}. "
                    f"Is the server running at {server_url}?"
                )
                return

        print()
        print(f"  {colorize('Controls:', 'bold')}")
        print(f"    {colorize('1-5', 'cyan')}  Toggle device-01 through device-05 on/off")
        print(f"    {colorize('q', 'cyan')}    Quit simulator")
        print()
        print(f"  {colorize('Sending heartbeats...', 'bold')}")
        print()

        # Step 2: Run heartbeat loop and input listener concurrently
        await asyncio.gather(
            heartbeat_loop(session, server_url, devices, stop_event),
            input_listener(devices, stop_event),
        )

    # Final status
    print()
    print_status_table(devices)
    print(f"  {colorize('Simulator stopped.', 'yellow')}")
    print()


def cli() -> None:
    """Parse CLI arguments and run the simulator."""
    parser = argparse.ArgumentParser(
        description="Simulate devices sending heartbeats to the fleet monitor."
    )
    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=f"Fleet monitor server URL (default: {DEFAULT_SERVER_URL})",
    )
    args = parser.parse_args()
    asyncio.run(main(args.server_url))


if __name__ == "__main__":
    cli()
