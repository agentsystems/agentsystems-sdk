"""View logs from AgentSystems services."""

from __future__ import annotations

import pathlib
from typing import Optional

import typer
from rich.console import Console

from ..utils import (
    ensure_docker_installed,
    compose_args,
    run_command,
)

console = Console()


def logs_command(
    service: Optional[str] = typer.Argument(
        None,
        help="Service name (e.g., gateway, postgres). If omitted, shows all services.",
    ),
    project_dir: pathlib.Path = typer.Option(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to agent-platform-deployments",
    ),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Follow log output (like tail -f)"
    ),
    tail: int = typer.Option(100, "--tail", help="Number of lines to show"),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
) -> None:
    """Stream logs from services (similar to `docker compose logs`).

    Examples:
      agentsystems logs           # all services
      agentsystems logs gateway   # just the gateway
      agentsystems logs -f        # follow all logs
    """
    ensure_docker_installed()

    compose_args_list = compose_args(project_dir, langfuse=not no_langfuse)

    cmd = [*compose_args_list, "logs", f"--tail={tail}"]

    if follow:
        cmd.append("-f")

    if service:
        cmd.append(service)

    run_command(cmd)
