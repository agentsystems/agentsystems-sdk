"""Restart AgentSystems services."""

from __future__ import annotations

import pathlib
from typing import Optional

import typer
from rich.console import Console

from .up import up_command, AgentStartMode

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
    agents_mode: AgentStartMode = typer.Option(
        AgentStartMode.create,
        "--agents",
        help="Agent startup mode: all (start), create (pull & create containers stopped), none (skip agents)",
        show_default=True,
    ),
    env_file: Optional[pathlib.Path] = typer.Option(
        None,
        "--env-file",
        help="Custom .env file passed to docker compose",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
):
    """Full platform restart with fresh agent containers and updated configuration.

    This is now an alias for `agentsystems up` since up always performs a clean
    down → up sequence. Kept for backwards compatibility.
    """
    console.print("[cyan]🔄 Full platform restart (down → up)[/cyan]")

    # up now handles the full down → up sequence
    up_command(
        project_dir=project_dir,
        detach=detach,
        fresh=False,
        wait_ready=wait_ready,
        no_langfuse=no_langfuse,
        agents_mode=agents_mode,
        env_file=env_file,
        agent_control_plane_version=None,
        agentsystems_ui_version=None,
    )
