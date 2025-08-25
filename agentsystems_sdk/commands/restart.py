"""Restart AgentSystems services."""

from __future__ import annotations

import pathlib
from typing import Optional

import typer
from rich.console import Console

from .down import down_command
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

    This is equivalent to `agentsystems down && agentsystems up` and will:
    - Stop all services and remove agent containers
    - Clean up unused networks
    - Start services with fresh agent containers using current .env and config

    Perfect for picking up configuration changes (API keys, model connections, etc.).
    """
    console.print("[cyan]🔄 Full platform restart (down → up)[/cyan]")

    # Call down command with default settings
    down_command(
        project_dir=project_dir,
        delete_volumes=False,
        delete_containers=False,  # Cleanup is now automatic
        delete_all=False,
        volumes=None,
        no_langfuse=no_langfuse,
    )

    # Call up command with all the same options
    up_command(
        project_dir=project_dir,
        detach=detach,
        fresh=False,  # Down already cleaned up
        wait_ready=wait_ready,
        no_langfuse=no_langfuse,
        agents_mode=agents_mode,
        env_file=env_file,
        agent_control_plane_version=None,
        agentsystems_ui_version=None,
    )
