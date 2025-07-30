"""Restart AgentSystems services."""

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


def restart_command(
    service: Optional[str] = typer.Argument(
        None,
        help="Service name to restart. If omitted, restarts all services.",
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
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
) -> None:
    """Restart service(s).

    Examples:
      agentsystems restart           # restart all services
      agentsystems restart gateway   # restart just the gateway
    """
    ensure_docker_installed()

    compose_args_list = compose_args(project_dir, langfuse=not no_langfuse)

    cmd = [*compose_args_list, "restart"]

    if service:
        cmd.append(service)
        console.print(f"[cyan]↻ Restarting {service}...[/cyan]")
    else:
        console.print("[cyan]↻ Restarting all services...[/cyan]")

    run_command(cmd)

    console.print("[green]✓ Restart complete[/green]")
