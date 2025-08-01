"""Stop the AgentSystems platform."""

from __future__ import annotations

import os
import pathlib
from typing import Optional

import docker
import typer
from rich.console import Console

from ..utils import (
    ensure_docker_installed,
    compose_args,
    run_command_with_env,
)

console = Console()


def down_command(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    delete_volumes: bool = typer.Option(
        False,
        "--delete-volumes",
        "-v",
        help="Also remove named volumes (data will be lost)",
    ),
    delete_containers: bool = typer.Option(
        False,
        "--delete-containers",
        help="Remove standalone agent containers (label agent.enabled=true)",
    ),
    delete_all: bool = typer.Option(
        False,
        "--delete-all",
        help="Remove volumes and agent containers in addition to the core stack",
    ),
    # Legacy flag (hidden) – maps to --delete-volumes for back-compat
    volumes: Optional[bool] = typer.Option(
        None,
        "--volumes/--no-volumes",
        help="[DEPRECATED] Use --delete-volumes instead",
        hidden=True,
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
) -> None:
    """Stop the platform.

    By default this stops and removes the docker-compose services but **retains**
    their named volumes, so database/object-store data are preserved.

    Use additional flags to purge data or standalone agent containers:
      --delete-volumes      remove named volumes (data loss)
      --delete-containers   remove agent containers created with `docker run`
      --delete-all          convenience flag = both of the above
    """
    ensure_docker_installed()

    # Map deprecated flag
    if volumes is not None:
        if volumes:
            delete_volumes = True
        typer.secho(
            "[DEPRECATED] --volumes/--no-volumes is deprecated; use --delete-volumes",
            fg=typer.colors.YELLOW,
        )

    # Promote --delete-all
    if delete_all:
        delete_volumes = True
        delete_containers = True

    # Stop compose services
    core_compose, compose_args_list = compose_args(
        project_dir, langfuse=not no_langfuse
    )
    cmd: list[str] = [*compose_args_list, "down"]
    if delete_volumes:
        cmd.append("-v")

    console.print("[cyan]⏻ Stopping core services…[/cyan]")
    run_command_with_env(cmd, os.environ.copy())

    # Remove agent containers if requested
    if delete_containers:
        client = docker.from_env()
        for c in client.containers.list(filters={"label": "agent.enabled=true"}):
            console.print(f"[cyan]⏻ Removing agent container {c.name}…[/cyan]")
            try:
                c.remove(force=True)
            except Exception as exc:
                console.print(f"[red]Failed to remove {c.name}: {exc}[/red]")

    console.print(
        "[green]✓ Platform stopped."
        + (" Volumes deleted." if delete_volumes else "")
        + (" Agent containers removed." if delete_containers else "")
        + "[/green]"
    )
