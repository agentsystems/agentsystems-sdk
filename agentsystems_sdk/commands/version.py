"""Version information command for AgentSystems SDK."""

from __future__ import annotations

import importlib.metadata
from rich.console import Console
from rich.table import Table

console = Console()


def version_command() -> None:
    """Display SDK version information only.

    For all component versions, use 'agentsystems versions'.
    """
    # Just show SDK version
    try:
        sdk_version = importlib.metadata.version("agentsystems-sdk")
    except importlib.metadata.PackageNotFoundError:
        sdk_version = "unknown (development mode)"
    console.print(f"AgentSystems SDK: {sdk_version}")


def versions_command() -> None:
    """Display version information for all AgentSystems components.

    Queries the running deployment to show current versions and update status.
    Only works when a deployment is running.
    """
    table = Table(title="AgentSystems Component Versions")
    table.add_column("Component", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Status", style="yellow")

    # SDK version
    try:
        sdk_version = importlib.metadata.version("agentsystems-sdk")
        table.add_row("AgentSystems SDK", sdk_version, "✓ Installed")
    except importlib.metadata.PackageNotFoundError:
        table.add_row("AgentSystems SDK", "unknown", "⚠ Development mode")

    # Try to query running deployment for gateway and UI versions
    try:
        import requests

        resp = requests.get("http://localhost:18080/component-versions", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            components = data.get("components", {})

            # Agent Control Plane
            acp = components.get("agent-control-plane", {})
            acp_version = acp.get("current_version", "unknown")
            acp_update = acp.get("update_available", False)
            acp_status = "✓ Running" + (
                " (update available)" if acp_update else " (latest)"
            )
            table.add_row("Agent Control Plane", acp_version, acp_status)

            # AgentSystems UI
            ui = components.get("agentsystems-ui", {})
            ui_version = ui.get("current_version", "unknown")
            ui_update = ui.get("update_available", False)
            ui_status = "✓ Running" + (
                " (update available)" if ui_update else " (latest)"
            )
            table.add_row("AgentSystems UI", ui_version, ui_status)

        else:
            table.add_row(
                "Agent Control Plane", "unknown", "⚠ Deployment not accessible"
            )
            table.add_row("AgentSystems UI", "unknown", "⚠ Deployment not accessible")

    except Exception:
        # Deployment not running or not accessible
        table.add_row("Agent Control Plane", "N/A", "⚠ Deployment not running")
        table.add_row("AgentSystems UI", "N/A", "⚠ Deployment not running")

    console.print(table)
    # Note: Simple check since Rich table internals are complex
    if "⚠" in str(table):
        console.print(
            "\n[dim]Note: Start deployment with 'agentsystems up' to check running versions[/dim]"
        )
