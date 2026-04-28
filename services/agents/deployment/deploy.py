"""Deployment script for slate-agents on Vertex AI Agent Engine.

Uses the Vertex AI Python SDK directly (vertexai.agent_engines) instead of
`adk deploy agent_engine` CLI, which has a bug in 1.31.x where deploymentSpec
is serialized empty causing 500 INTERNAL from the Vertex AI API.

Usage:
    python deployment/deploy.py --validate
    python deployment/deploy.py --create
    python deployment/deploy.py --update --resource-id <id>
    python deployment/deploy.py --health --resource-id <id>
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = [
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "STAGING_BUCKET",
    "ROOT_AGENT_MODEL",
    "SLATE_API_URL",
]

REQUIREMENTS: list[str] = [
    "google-cloud-aiplatform[adk,agent_engines]>=1.118.0",
    "google-adk>=1.31.1",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
]

_RUNTIME_VAR_NAMES = [
    "GOOGLE_GENAI_USE_VERTEXAI",
    "ROOT_AGENT_MODEL",
    "SLATE_API_URL",
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


def _build_adk_app():  # type: ignore[return]
    """Wrap the App object in AdkApp for Agent Engine deployment."""
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from vertexai.agent_engines import AdkApp  # type: ignore[import-untyped]

    from slate_agents import app  # App-wrapped root agent

    return AdkApp(app=app, enable_tracing=True)


def _env_vars() -> dict[str, str]:
    return {k: os.environ[k] for k in _RUNTIME_VAR_NAMES if k in os.environ}


def _versioned_name(base: str) -> str:
    version = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    git_sha = os.getenv("GITHUB_SHA", "local")[:7]
    return f"{base}-v{version}-{git_sha}"


def create_agent() -> str:
    """Create a new Agent Engine instance. Prints the numeric ID to stdout."""
    import cloudpickle  # type: ignore[import-untyped]
    import vertexai  # type: ignore[import-untyped]
    from vertexai import agent_engines  # type: ignore[import-untyped]

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    staging_bucket = os.environ["STAGING_BUCKET"]
    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    adk_app = _build_adk_app()

    # Verify the AdkApp is pickleable before attempting remote deployment.
    pickle_size = len(cloudpickle.dumps(adk_app))
    logger.info("AdkApp pickle size: %d bytes (staging_bucket=%s)", pickle_size, staging_bucket)

    display_name = _versioned_name("slate-agents-dev")

    logger.info("Creating Agent Engine: %s", display_name)
    remote = agent_engines.create(
        agent_engine=adk_app,
        requirements=REQUIREMENTS,
        display_name=display_name,
        env_vars=_env_vars(),
    )
    name = remote.gca_resource.name
    logger.info("Created Agent Engine: %s", name)
    return name


def update_agent(resource_id: str) -> str:
    """Update an existing Agent Engine instance. Prints the numeric ID to stdout."""
    import cloudpickle  # type: ignore[import-untyped]
    import vertexai  # type: ignore[import-untyped]
    from vertexai import agent_engines  # type: ignore[import-untyped]

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    staging_bucket = os.environ["STAGING_BUCKET"]
    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    resource_name = (
        f"projects/{project}/locations/{location}/reasoningEngines/{resource_id}"
        if not resource_id.startswith("projects/")
        else resource_id
    )

    adk_app = _build_adk_app()

    # Verify the AdkApp is pickleable before attempting remote deployment.
    pickle_size = len(cloudpickle.dumps(adk_app))
    logger.info("AdkApp pickle size: %d bytes (staging_bucket=%s)", pickle_size, staging_bucket)

    display_name = _versioned_name("slate-agents-dev")

    logger.info("Updating Agent Engine: %s → %s", resource_name, display_name)
    remote = agent_engines.update(
        resource_name=resource_name,
        agent_engine=adk_app,
        requirements=REQUIREMENTS,
        display_name=display_name,
        env_vars=_env_vars(),
    )
    name = remote.gca_resource.name
    logger.info("Updated Agent Engine: %s", name)
    return name


def health_check(resource_id: str) -> bool:
    """Verify that the deployed Agent Engine is reachable via the high-level SDK.

    The v1beta1 ReasoningEngine proto has no `state` field — lifecycle state is
    not exposed in that API. Instead we use vertexai.agent_engines.get() which
    resolves the LRO and raises if the engine is not yet active or does not exist.
    """
    try:
        import vertexai  # type: ignore[import-untyped]
        from vertexai import agent_engines  # type: ignore[import-untyped]

        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ["GOOGLE_CLOUD_LOCATION"]
        vertexai.init(
            project=project, location=location, staging_bucket=os.environ["STAGING_BUCKET"]
        )

        resource_name = (
            f"projects/{project}/locations/{location}/reasoningEngines/{resource_id}"
            if not resource_id.startswith("projects/")
            else resource_id
        )

        engine = agent_engines.get(resource_name)
        display_name = engine.display_name
        logger.info("Agent Engine reachable: %s (%s)", resource_name, display_name)
        logger.info("Health check PASSED.")
        return True

    except Exception as e:
        logger.error("Health check FAILED — %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="slate-agents deployment")
    parser.add_argument("--validate", action="store_true", help="Validate env vars")
    parser.add_argument("--create", action="store_true", help="Create new Agent Engine")
    parser.add_argument("--update", action="store_true", help="Update existing Agent Engine")
    parser.add_argument("--health", action="store_true", help="Post-deploy health check")
    parser.add_argument("--resource-id", help="Agent Engine numeric ID (for --update/--health)")
    args = parser.parse_args()

    if args.validate:
        if not validate():
            sys.exit(1)
        return

    if args.create:
        name = create_agent()
        print(name.split("/")[-1])  # numeric ID only — caller greps this
        return

    if args.update:
        if not args.resource_id:
            logger.error("--resource-id is required for --update")
            sys.exit(1)
        name = update_agent(args.resource_id)
        print(name.split("/")[-1])
        return

    if args.health:
        if not args.resource_id:
            logger.error("--resource-id is required for --health")
            sys.exit(1)
        if not health_check(args.resource_id):
            sys.exit(1)
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
