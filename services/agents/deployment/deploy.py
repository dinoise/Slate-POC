"""Deployment script for slate-agents on Vertex AI Agent Engine.

Uses vertexai.Client (new client-based API) instead of agent_engines module
functions.

Must be run from services/agents/ directory (default in CI via working-directory).

extra_packages uses a directory path ("./src/slate_agents") so Agent Engine copies
the package to /code/slate_agents/ inside the container. /code/ is on sys.path,
making `slate_agents` importable by both cloudpickle and the control plane's
python_file_api_builder — without requiring a virtualenv install.

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
    "httpx>=0.28.0",
    "google-auth>=2.36.0",
]

# Directory relative to services/agents/ — Agent Engine copies it to /code/slate_agents/
# inside the container. /code/ is on sys.path, so `slate_agents` is importable by
# both cloudpickle unpickling and the control plane's python_file_api_builder.
EXTRA_PACKAGES: list[str] = ["./slate_agents"]

_RUNTIME_VAR_NAMES = [
    "GOOGLE_GENAI_USE_VERTEXAI",
    "ROOT_AGENT_MODEL",
    "SLATE_API_URL",
]


def validate() -> bool:
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return False
    logger.info("All required environment variables are set.")
    return True


def _service_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _build_adk_app():  # type: ignore[return]
    # slate_agents is now at services/agents/slate_agents/ (no src/ layout).
    # Add the service root so `import slate_agents` resolves locally the same
    # way Agent Engine resolves it remotely (/code/slate_agents/).
    service_root = _service_root()
    if service_root not in sys.path:
        sys.path.insert(0, service_root)

    from vertexai.agent_engines import AdkApp  # type: ignore[import-untyped]

    from slate_agents import app  # App-wrapped root agent

    return AdkApp(app=app, enable_tracing=True)


def _env_vars() -> dict[str, str]:
    return {k: os.environ[k] for k in _RUNTIME_VAR_NAMES if k in os.environ}


def _versioned_name(base: str) -> str:
    version = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    git_sha = os.getenv("GITHUB_SHA", "local")[:7]
    return f"{base}-v{version}-{git_sha}"


def _init_client():  # type: ignore[return]
    import vertexai  # type: ignore[import-untyped]

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    return vertexai.Client(project=project, location=location)


def create_agent() -> str:
    staging_bucket = os.environ["STAGING_BUCKET"]
    client = _init_client()
    adk_app = _build_adk_app()
    display_name = _versioned_name("slate-agents-dev")

    logger.info("Creating Agent Engine: %s", display_name)
    remote = client.agent_engines.create(
        agent=adk_app,
        config={
            "staging_bucket": staging_bucket,
            "display_name": display_name,
            "requirements": REQUIREMENTS,
            "extra_packages": EXTRA_PACKAGES,
            "env_vars": _env_vars(),
        },
    )
    name = remote.api_resource.name
    logger.info("Created Agent Engine: %s", name)
    return name


def update_agent(resource_id: str) -> str:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    staging_bucket = os.environ["STAGING_BUCKET"]

    resource_name = (
        f"projects/{project}/locations/{location}/reasoningEngines/{resource_id}"
        if not resource_id.startswith("projects/")
        else resource_id
    )

    client = _init_client()
    adk_app = _build_adk_app()
    display_name = _versioned_name("slate-agents-dev")

    logger.info("Updating Agent Engine: %s → %s", resource_name, display_name)
    remote = client.agent_engines.update(
        name=resource_name,
        agent=adk_app,
        config={
            "staging_bucket": staging_bucket,
            "display_name": display_name,
            "requirements": REQUIREMENTS,
            "extra_packages": EXTRA_PACKAGES,
            "env_vars": _env_vars(),
        },
    )
    name = remote.api_resource.name
    logger.info("Updated Agent Engine: %s", name)
    return name


def health_check(resource_id: str) -> bool:
    try:
        client = _init_client()
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ["GOOGLE_CLOUD_LOCATION"]
        resource_name = (
            f"projects/{project}/locations/{location}/reasoningEngines/{resource_id}"
            if not resource_id.startswith("projects/")
            else resource_id
        )
        engine = client.agent_engines.get(name=resource_name)
        display_name = getattr(engine, "display_name", None) or getattr(
            getattr(engine, "api_resource", None), "display_name", resource_name
        )
        logger.info("Agent Engine reachable: %s (%s)", resource_name, display_name)
        logger.info("Health check PASSED.")
        return True
    except Exception as e:
        logger.error("Health check FAILED — %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="slate-agents deployment")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--resource-id")
    args = parser.parse_args()

    if args.validate:
        if not validate():
            sys.exit(1)
        return

    if args.create:
        name = create_agent()
        print(name.split("/")[-1])
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
