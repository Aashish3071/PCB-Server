# Virtual Device Simulator

## Architecture Overview
The Virtual Device Simulator is a standalone Python application designed to emulate a fleet of IoT devices communicating with the backend platform. It operates entirely independently of the backend codebase, utilizing asynchronous HTTP requests to simulate realistic network activity, device lifecycles, telemetry payloads, and edge-case failure scenarios.

## Folder Structure
- `config/`: YAML configurations defining simulation environments (`development.yaml`, `load-test.yaml`, etc.).
- `devices/`: Core models for Virtual Devices and the Fleet Manager.
- `exports/`: Storage for JSON/CSV exports and simulation benchmark reports.
- `logs/`: Persistent JSON logs matching the backend's `structlog` format.
- `payloads/`: Builder utilities for constructing standard and malformed HTTP payloads.
- `profiles/`: Configuration logic for device profiles (e.g., Urban, Industrial).
- `scenarios/`: Modular failure engines for injecting specific conditions (e.g., Offline, Low Battery).
- `state/`: Persistent runtime state storage (offline buffering, provisioning caches, replay data).
- `tests/`: Automated test suite for the simulator itself.

## Configuration
Configurations are managed via YAML files located in the `config/` directory.

Base settings include:
- `backend`: Backend API URL target.
- `fleet`: Size and deployment strategies.
- `telemetry`: Upload intervals and payload parameters.
- `simulation`: Speed multipliers and deterministic random seeds.
- `logging`: Output levels.

## Running the Simulator
To run the simulator locally, use the unified `Makefile` at the project root:

```bash
make start-simulator
```

Or manually using `uv`:
```bash
uv run python main.py --config config/development.yaml
```

## Available Scenarios
*(To be implemented in later features)*
- **Offline**: Simulates network drops and builds up offline queues.
- **Low Battery**: Injects steep battery drain payloads.
- **Clock Drift**: Simulates RTC desynchronization causing future/past timestamps.

## Troubleshooting
- **Configuration Load Error**: Verify that the `--config` path passed to `main.py` is correct and relative to the `simulator/` directory.
- **Backend Connection Failed**: Ensure the backend server is running (`make start-backend`) and matches the URL specified in the config.

## Development Workflow
Use the root `Makefile` to lint, format, and test the simulator along with the rest of the project:
- `make format-python`
- `make lint`
- `make test-simulator`
