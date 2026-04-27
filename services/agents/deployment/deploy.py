"""Deployment helper for slate-agents.

This script is a complement to `adk deploy agent_engine` — it provides
pre-deploy validation and post-deploy health checks.

Usage:
    # Validate env vars before deploying
    python deployment/deploy.py --validate

    # Check Agent Engine health after deploy
    python deployment/deploy.py --health --agent-engine-id <id>

    # Full validate + deploy + health check (called by CI workflow)
    python deployment/deploy.py --validate
    adk deploy agent_engine ...
    python deployment/deploy.py --health --agent-engine-id <id>

Note: The actual deploy is handled by `adk deploy agent_engine` CLI.
This script only handles validation and health checks.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "ROOT_AGENT_MODEL",
    "SLATE_API_URL",
    "GCS_STAGING_BUCKET",
]


def validate() -> bool:
    """Check that all required environment variables are set."""
    logger.info("Validating environment variables...")
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return False
    logger.info("All required environment variables are set.")
    return True


def health_check(agent_engine_id: str) -> bool:
    """Verify that the deployed Agent Engine is in ACTIVE state."""
    try:
        import vertexai  # type: ignore[import-untyped]

        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ["GOOGLE_CLOUD_LOCATION"]

        logger.info("Checking Agent Engine health: %s", agent_engine_id)
        vertexai.init(project=project, location=location)

        # Use the ReasoningEngine resource to check state
        from google.cloud.aiplatform_v1beta1 import (
            ReasoningEngineServiceClient,  # type: ignore[import-untyped]
        )

        client = ReasoningEngineServiceClient()
        resource_name = (
            f"projects/{project}/locations/{location}/reasoningEngines/{agent_engine_id}"
        )
        engine = client.get_reasoning_engine(name=resource_name)

        state = engine.state.name if hasattr(engine, "state") else "UNKNOWN"
        logger.info("Agent Engine state: %s", state)

        if state == "ACTIVE":
            logger.info("Health check PASSED.")
            return True
        else:
            logger.error("Health check FAILED — unexpected state: %s", state)
            return False

    except Exception as e:
        logger.error("Health check error: %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="slate-agents deployment helper")
    parser.add_argument("--validate", action="store_true", help="Validate env vars")
    parser.add_argument("--health", action="store_true", help="Post-deploy health check")
    parser.add_argument("--agent-engine-id", help="Agent Engine ID for health check")
    args = parser.parse_args()

    if args.validate:
        if not validate():
            sys.exit(1)

    if args.health:
        if not args.agent_engine_id:
            logger.error("--agent-engine-id is required for health check")
            sys.exit(1)
        if not health_check(args.agent_engine_id):
            sys.exit(1)

    if not args.validate and not args.health:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
