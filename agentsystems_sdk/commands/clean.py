"""Clean up AgentSystems resources."""

from __future__ import annotations

import pathlib

import docker
import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def clean_command(
    project_dir: pathlib.Path = typer.Option(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to agent-platform-deployments",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts",
    ),
) -> None:
    """Remove ALL AgentSystems containers, volumes, and networks.

    This is a destructive operation that will:
    - Stop and remove all containers (compose and agents)
    - Delete all volumes (including data)
    - Remove the agents_net network

    Use with caution!
    """
    if not force:
        console.print(
            Panel.fit(
                "[bold red]⚠️  WARNING ⚠️[/bold red]\n\n"
                "This will remove ALL AgentSystems resources:\n"
                "• All containers (core services and agents)\n"
                "• All volumes (databases, artifacts, etc.)\n"
                "• The agents_net network\n\n"
                "[bold]All data will be permanently deleted![/bold]",
                border_style="red",
            )
        )

        confirm = typer.confirm("Are you sure you want to continue?", default=False)
        if not confirm:
            console.print("[yellow]Operation cancelled.[/yellow]")
            raise typer.Exit(code=0)

    try:
        client = docker.from_env()
    except Exception:
        typer.secho("Docker not available", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # First, use the down command to stop compose services
    from .down import down_command

    console.print("[cyan]Stopping compose services...[/cyan]")
    down_command(
        project_dir=project_dir,
        delete_volumes=True,
        delete_containers=True,
        delete_all=True,
        volumes=None,
        no_langfuse=False,
    )

    # Remove any remaining agentsystems containers
    console.print("\n[cyan]Removing any remaining containers...[/cyan]")
    for container in client.containers.list(all=True):
        if "agentsystems" in container.name or "agent.enabled" in container.labels:
            console.print(f"  Removing {container.name}")
            try:
                container.remove(force=True)
            except Exception as e:
                console.print(f"  [red]Failed to remove {container.name}: {e}[/red]")

    # Remove volumes
    console.print("\n[cyan]Removing volumes...[/cyan]")
    for volume in client.volumes.list():
        if volume.name.startswith("agentsystems"):
            console.print(f"  Removing volume {volume.name}")
            try:
                volume.remove(force=True)
            except Exception as e:
                console.print(f"  [red]Failed to remove {volume.name}: {e}[/red]")

    # Remove network
    console.print("\n[cyan]Removing network...[/cyan]")
    try:
        net = client.networks.get("agents_net")
        console.print("  Removing network agents_net")
        net.remove()
    except docker.errors.NotFound:
        console.print("  Network agents_net not found")
    except Exception as e:
        console.print(f"  [red]Failed to remove network: {e}[/red]")

    console.print("\n[green]✓ Cleanup complete![/green]")
