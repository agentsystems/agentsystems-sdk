"""View logs from AgentSystems services."""

from __future__ import annotations

import os
import pathlib
from typing import List, Optional

import typer

from ..utils import ensure_docker_installed, compose_args, run_command_with_env


def logs_command(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    follow: bool = typer.Option(
        True, "--follow/--no-follow", "-f", help="Follow log output"
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
    services: Optional[List[str]] = typer.Argument(
        None, help="Optional list of services to show logs for"
    ),
) -> None:
    """Stream (or dump) logs from docker compose services."""
    ensure_docker_installed()
    core_compose, compose_args_list = compose_args(
        project_dir, langfuse=not no_langfuse
    )
    cmd = [*compose_args_list, "logs"]
    if follow:
        cmd.append("-f")
    if services:
        cmd.extend(services)
    run_command_with_env(cmd, os.environ.copy())
