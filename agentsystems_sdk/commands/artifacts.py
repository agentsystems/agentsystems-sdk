"""Manage artifacts directory for AgentSystems."""

from __future__ import annotations

import pathlib

import docker
import typer
from rich.console import Console

console = Console()


def artifacts_path_command(
    thread_id: str = typer.Argument(..., help="Thread ID to resolve"),
    subdir: str = typer.Option("in", help="Subdirectory: 'in' or 'out'"),
) -> None:
    """Get the file path for a given thread's artifacts directory.

    Outputs the absolute path on the host filesystem where artifacts for the given
    thread ID are stored. Useful for scripts that need to access uploaded/generated files.

    The 'in' subdirectory contains uploaded files.
    The 'out' subdirectory contains agent-generated files.
    """
    try:
        client = docker.from_env()
    except Exception:
        typer.secho("Docker not available", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Find the artifacts volume
    try:
        volume = client.volumes.get("agentsystems_artifacts")
        mount_point = volume.attrs.get("Mountpoint", "")

        if not mount_point:
            typer.secho(
                "Could not determine artifacts volume mount point",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

        # Construct the full path
        artifact_path = pathlib.Path(mount_point) / thread_id / subdir

        # Output just the path (for scripting)
        typer.echo(str(artifact_path))

    except docker.errors.NotFound:
        typer.secho(
            "Artifacts volume not found. Is the platform running?",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
