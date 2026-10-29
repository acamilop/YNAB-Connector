"""YNAB MCP Server using FastMCP and OpenAPI specification."""

import os
from pathlib import Path

import httpx
import yaml
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import MCPType, OpenAPITool, RouteMap

YNAB_API_BASE = "https://api.ynab.com/v1"
YNAB_OPENAPI_SPEC_URL = "https://api.ynab.com/papi/open_api_spec.yaml"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Routes to exclude from the MCP server (these return too much data and bomb the context)
EXCLUDED_ROUTES = [
    RouteMap(
        methods=["GET"],
        pattern=r"^/budgets/\{budget_id\}/payees$",
        mcp_type=MCPType.EXCLUDE,
    ),
]


def _omit_openapi_output_schemas(_route: object, component: object) -> None:
    """Cursor rejects some YNAB OpenAPI response schemas; tools do not need them."""
    if isinstance(component, OpenAPITool):
        component.output_schema = None


def _load_env_file(path: Path = ENV_FILE) -> None:
    """Set KEY=value pairs from the checkout's .env without overriding the real environment."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def create_server() -> FastMCP:
    """Create and configure the YNAB MCP server from the OpenAPI spec."""
    _load_env_file()
    token = os.environ.get("YNAB_API_TOKEN")
    if not token:
        raise ValueError(
            f"YNAB_API_TOKEN is required. Add it to {ENV_FILE} or set it as an environment variable. "
            "Get your personal access token from https://app.ynab.com/settings/developer"
        )

    # Fetch the OpenAPI spec from YNAB
    spec_response = httpx.get(YNAB_OPENAPI_SPEC_URL)
    spec_response.raise_for_status()
    openapi_spec = yaml.safe_load(spec_response.text)

    # Create an authenticated HTTP client
    client = httpx.AsyncClient(
        base_url=YNAB_API_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )

    # Create MCP server from OpenAPI spec
    return FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="YNAB MCP Server",
        route_maps=EXCLUDED_ROUTES,
        mcp_component_fn=_omit_openapi_output_schemas,
    )


def main() -> None:
    """Run the YNAB MCP server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
