"""Show status of AgentSystems services."""

from __future__ import annotations

import pathlib

import docker
import typer
from rich.console import Console
from rich.table import Table

from ..utils import ensure_docker_installed

console = Console()


def status_command(
    project_dir: pathlib.Path = typer.Option(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to agent-platform-deployments",
    ),
) -> None:
    """Show status of platform containers (both compose and standalone agents)."""
    ensure_docker_installed()

    client = docker.from_env()

    # Create status table
    table = Table(title="AgentSystems Platform Status")
    table.add_column("Container", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Health")
    table.add_column("Ports")

    # Get all containers with agentsystems prefix or agent label
    compose_containers = client.containers.list(
        all=True, filters={"name": "agentsystems"}
    )
    agent_containers = client.containers.list(
        all=True, filters={"label": "agent.enabled=true"}
    )

    # Combine and deduplicate
    all_containers = {c.id: c for c in compose_containers + agent_containers}.values()

    for container in sorted(all_containers, key=lambda c: c.name):
        # Determine type
        if "agent.enabled" in container.labels:
            container_type = "Agent"
        elif "agentsystems" in container.name:
            container_type = "Core"
        else:
            container_type = "Other"

        # Get status
        status = container.status.capitalize()
        if status == "Running":
            status = f"[green]{status}[/green]"
        elif status == "Exited":
            status = f"[red]{status}[/red]"
        else:
            status = f"[yellow]{status}[/yellow]"

        # Get health status
        health = "-"
        if container.status == "running" and "Health" in container.attrs["State"]:
            health_status = container.attrs["State"]["Health"]["Status"]
            if health_status == "healthy":
                health = "[green]Healthy[/green]"
            elif health_status == "unhealthy":
                health = "[red]Unhealthy[/red]"
            else:
                health = f"[yellow]{health_status}[/yellow]"

        # Get ports
        ports = []
        if container.attrs["NetworkSettings"]["Ports"]:
            for container_port, host_ports in container.attrs["NetworkSettings"][
                "Ports"
            ].items():
                if host_ports:
                    for hp in host_ports:
                        ports.append(f"{hp['HostPort']}→{container_port}")
        port_str = ", ".join(ports) if ports else "-"

        table.add_row(
            container.name,
            container_type,
            status,
            health,
            port_str,
        )

    console.print(table)

    # Show summary
    running_count = sum(1 for c in all_containers if c.status == "running")
    total_count = len(all_containers)

    console.print(
        f"\n[bold]Summary:[/bold] {running_count}/{total_count} containers running"
    )
