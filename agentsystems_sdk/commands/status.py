"""Show status of AgentSystems services."""

from __future__ import annotations

import os
import pathlib

import typer

from ..utils import ensure_docker_installed, compose_args, run_command_with_env


def status_command(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
):
    """List running containers and their state (`docker compose ps`)."""
    ensure_docker_installed()
    core_compose, compose_args_list = compose_args(
        project_dir, langfuse=not no_langfuse
    )
    cmd = [*compose_args_list, "ps"]
    run_command_with_env(cmd, os.environ.copy())
