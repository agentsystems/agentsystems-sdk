"""Restart AgentSystems services."""

from __future__ import annotations

import os
import pathlib

import typer
from rich.console import Console

from ..utils import (
    ensure_docker_installed,
    compose_args,
    run_command_with_env,
    wait_for_gateway_ready,
)

console = Console()


def restart_command(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--foreground",
        "-d",
        help="Run containers in background (default) or stream logs in foreground",
    ),
    wait_ready: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="After start, wait until gateway is ready (detached mode only)",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse tracing stack"
    ),
):
    """Quick bounce: `down` → `up` (non-destructive).

    Retains data volumes; wipe with `down --delete-volumes` first.
    Useful during development and CI.
    """
    ensure_docker_installed()
    core_compose, compose_args_list = compose_args(
        project_dir, langfuse=not no_langfuse
    )
    env = os.environ.copy()

    # Stop current stack
    cmd_down: list[str] = [*compose_args_list, "down"]
    console.print("[cyan]⏻ Stopping core services…[/cyan]")
    run_command_with_env(cmd_down, env)

    # Start stack again
    cmd_up: list[str] = [*compose_args_list, "up"]
    if detach:
        cmd_up.append("-d")
    console.print("[cyan]⏫ Starting core services…[/cyan]")
    run_command_with_env(cmd_up, env)

    # Optional readiness wait
    if wait_ready and detach:
        wait_for_gateway_ready()
    console.print("[green]✓ Restart complete.[/green]")
