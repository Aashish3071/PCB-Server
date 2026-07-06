import argparse
import sys
import yaml
import structlog
import asyncio
from typing import Dict, Any

def setup_logging(config: Dict[Any, Any]):
    """Initialize structured logging based on config."""
    log_level = config.get("logging", {}).get("level", "INFO").upper()
    
    # Map string level to standard logging levels
    import logging
    level = getattr(logging, log_level, logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )

def load_config(config_path: str) -> Dict[Any, Any]:
    """Load and parse YAML configuration."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"FAILED: Could not load configuration at {config_path}. Error: {e}")
        sys.exit(1)

def verify_dependencies():
    """Verify required dependencies are available."""
    try:
        import httpx
        import yaml
        import structlog
        import pydantic
    except ImportError as e:
        print(f"FAILED: Missing required dependency - {e}")
        sys.exit(1)

async def main():
    parser = argparse.ArgumentParser(description="Virtual Device Simulator")
    parser.add_argument("--config", type=str, default="config/default.yaml", help="Path to YAML configuration file")
    args = parser.parse_args()

    # 1. Verify dependencies
    verify_dependencies()

    # 2. Load config
    config = load_config(args.config)

    # 3. Initialize logging
    setup_logging(config)
    logger = structlog.get_logger()

    # 4. Verify Backend URL
    backend_url = config.get("backend", {}).get("url")
    if not backend_url:
        logger.error("Configuration error", missing_field="backend.url")
        sys.exit(1)
    
    simulator_version = config.get("simulator", {}).get("version", "unknown")
    fleet_size = config.get("fleet", {}).get("size", 0)

    # Display Startup Summary
    print("========================================")
    print(" VIRTUAL DEVICE SIMULATOR STARTING")
    print("========================================")
    print(f" Configuration : {args.config} loaded successfully.")
    print(f" Logging       : Initialized at {config.get('logging', {}).get('level', 'INFO')}")
    print(f" Backend URL   : {backend_url}")
    print(f" Fleet Size    : {fleet_size} devices")
    print(f" Sim Version   : {simulator_version}")
    print(" Dependencies  : Verified")
    print("========================================")
    
    # 5. Initialize and Start Fleet Manager
    from devices.fleet import FleetManager
    from telemetry_client import TransportClient

    transport = TransportClient(base_url=backend_url, verify_ssl=False)
    fleet = FleetManager(config=config, transport=transport)
    
    try:
        await fleet.initialize()
        await fleet.start()
    except Exception as e:
        logger.error("Fleet manager encountered an error", error=str(e))
    finally:
        await transport.close()
        logger.info("Simulator shutting down")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
