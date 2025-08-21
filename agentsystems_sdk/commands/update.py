"""Update core platform images."""

from __future__ import annotations

import pathlib
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..utils import ensure_docker_installed, run_command

console = Console()


def update_command(
    project_dir: Optional[pathlib.Path] = typer.Argument(
        None,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Project directory (defaults to current directory)",
    ),
) -> None:
    """Update core AgentSystems platform images to latest versions.

    Pulls the latest versions of:
    - agent-control-plane (gateway)
    - agentsystems-ui (web interface)

    This is faster than re-running 'agentsystems up' when you only need
    to update the core platform components.
    """
    if project_dir is None:
        project_dir = pathlib.Path.cwd()

    project_dir = project_dir.expanduser().resolve()

    # Verify this is an AgentSystems project
    config_file = project_dir / "agentsystems-config.yml"
    if not config_file.exists():
        console.print(f"[red]✗ No agentsystems-config.yml found in {project_dir}[/red]")
        console.print("This doesn't appear to be an AgentSystems project directory.")
        raise typer.Exit(code=1)

    ensure_docker_installed()

    # Core platform images to update
    core_images = [
        "ghcr.io/agentsystems/agent-control-plane:latest",
        "ghcr.io/agentsystems/agentsystems-ui:latest",
    ]

    console.print("\n[bold cyan]Updating AgentSystems core platform images[/bold cyan]")

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        console=console,
    ) as progress:

        for image in core_images:
            task = progress.add_task(f"Updating {image.split('/')[-1]}", total=None)

            try:
                progress.stop()  # Stop to show docker output
                run_command(["docker", "pull", image])
                progress.start()  # Restart progress
                progress.update(task, description=f"✓ Updated {image.split('/')[-1]}")
            except typer.Exit:
                progress.start()  # Ensure progress is restarted
                progress.update(
                    task, description=f"✗ Failed to update {image.split('/')[-1]}"
                )
                console.print(f"[red]Failed to pull {image}[/red]")
                raise
            finally:
                progress.start()  # Always ensure progress is running

    console.print("\n[green]✅ Core platform images updated successfully![/green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  • Run [cyan]agentsystems restart[/cyan] to use the updated images")
    console.print(
        "  • Or [cyan]agentsystems down && agentsystems up[/cyan] for a full restart"
    )
