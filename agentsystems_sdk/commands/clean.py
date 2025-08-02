"""Clean up AgentSystems resources."""

from __future__ import annotations

import os
import pathlib

import typer
from rich.console import Console

from ..utils import ensure_docker_installed, compose_args, run_command_with_env

console = Console()


def clean_command(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    prune_system: bool = typer.Option(
        True,
        "--prune-system/--no-prune-system",
        help="Also run 'docker system prune -f' to clear dangling images and networks",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack during cleanup"
    ),
) -> None:
    """Fully stop the platform, delete volumes, and prune Docker cache.

    This is the nuclear option that removes all containers, volumes, and optionally
    prunes the Docker system to reclaim disk space.

    Args:
        project_dir: Path to agent-platform-deployments directory
        prune_system: Whether to run docker system prune
        no_langfuse: Disable Langfuse stack during cleanup
    """
    ensure_docker_installed()
    core_compose, compose_args_list = compose_args(
        project_dir, langfuse=not no_langfuse
    )
    env = os.environ.copy()

    console.print("[cyan]⏻ Removing containers and volumes…[/cyan]")
    run_command_with_env([*compose_args_list, "down", "-v"], env)

    if prune_system:
        console.print("[cyan]🧹 Pruning Docker system…[/cyan]")
        try:
            run_command_with_env(["docker", "system", "prune", "-f"], env)
        except Exception:
            # Non-fatal if prune fails
            console.print("[yellow]⚠ Docker prune failed (non-fatal)[/yellow]")

    console.print("[green]✓ Cleanup complete.[/green]")
