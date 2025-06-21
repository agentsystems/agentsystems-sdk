"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

import os
import pathlib
import shutil
import subprocess
import sys
from typing import List, Optional

import typer

app = typer.Typer(help="AgentSystems command-line interface")


__version_str = _metadata.version("agentsystems-sdk")

def _version_callback(value: bool):  # noqa: D401 – simple callback
    if value:
        typer.echo(__version_str)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show the AgentSystems SDK version and exit.",
    ),
):
    """AgentSystems command-line interface."""
    # Callback body intentionally empty – options handled via callbacks.



@app.command()
def init(
    project_dir: Optional[pathlib.Path] = typer.Argument(None, exists=False, file_okay=False, dir_okay=True, writable=True, resolve_path=True),
    branch: str = typer.Option("main", help="Branch to clone"),
    ssh: bool = typer.Option(False, help="Clone via SSH instead of HTTPS"),
    token: str | None = typer.Option(None, "--token", help="Auth token for private repo / container registry"),
):
    """Clone the agent deployment template and pull required Docker images.

    Steps:
    1. Prompt for a project name (defaults to directory name).
    2. Clone the `agent-platform-deployments` template repo into *project_dir*.
    3. Pull Docker images required by the platform.
    """
    # Determine target directory
    if project_dir is None:
        if not sys.stdin.isatty():
            typer.secho("TARGET_DIR argument required when running non-interactively.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        default_dir = pathlib.Path.cwd() / "agent-platform-deployments"
        dir_input = typer.prompt("Directory to create", default=str(default_dir))
        project_dir = pathlib.Path(dir_input)

    project_dir = project_dir.expanduser()
    if project_dir.exists() and any(project_dir.iterdir()):
        typer.secho(f"Directory {project_dir} is not empty – aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Prompt for token if not provided
    if token is None and sys.stdin.isatty():
        token_input = typer.prompt("Registry access token (leave blank for none)", default="", hide_input=True)
        token = token_input or None

    repo_https = "https://github.com/agentsystems/agent-platform-deployments.git"
    repo_ssh = "git@github.com:agentsystems/agent-platform-deployments.git"
    repo = repo_ssh if ssh else repo_https
    if token and not ssh:
        # inject token into URL (supports GitHub PAT beginning with ghp_)
        repo = repo_https.replace("https://", f"https://{token}@")

    typer.echo(f"Cloning {repo} → {project_dir} (branch {branch})…")
    _run(["git", "clone", "--branch", branch, repo, str(project_dir)])

    typer.echo("Clone complete. Pulling Docker images (this may take a while)…")
    _ensure_docker_installed()
    _docker_login_if_needed(token)
    for img in _required_images():
        typer.echo(f"  → pulling {img}")
        _run(["docker", "pull", img])

    typer.secho("\nInitialization complete!", fg=typer.colors.GREEN)
    typer.echo(f"Navigate to {project_dir} and follow the README to start the platform.")


@app.command()
def version() -> None:
    """Display the installed SDK version."""
    typer.echo(_metadata.version("agentsystems-sdk"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str]) -> None:
    """Run *cmd* and stream output, aborting on non-zero exit."""
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        typer.secho(f"Command failed: {' '.join(cmd)}", fg=typer.colors.RED)
        raise typer.Exit(exc.returncode) from exc


def _ensure_docker_installed() -> None:
    if shutil.which("docker") is None:
        typer.secho("Docker CLI not found. Please install Docker Desktop and retry.", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _docker_login_if_needed(token: str | None) -> None:
    if not token:
        return
    registry = "docker.io"
    typer.echo("Logging into container registry…")
    _run(["docker", "login", registry, "-u", "oauth2", "-p", token])


def _required_images() -> List[str]:
    # Central place to keep image list – update when the platform adds new components.
    return [
        "agentsystems/agent-control-plane:latest",
        "agentsystems/agent-backend:latest",
    ]


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
