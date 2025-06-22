"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

import os
import pathlib
from dotenv import load_dotenv
import shutil
import subprocess
import sys
from typing import List, Optional

# Load .env before Typer parses env-var options
load_dotenv()

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
    gh_token: str | None = typer.Option(None, "--gh-token", envvar="GITHUB_TOKEN", help="GitHub Personal Access Token for private template repo"),
    docker_token: str | None = typer.Option(None, "--docker-token", envvar="DOCKER_OAT", help="Docker Hub Org Access Token for private images"),
):
    """Clone the agent deployment template and pull required Docker images.

    Steps:
    1. Clone the `agent-platform-deployments` template repo into *project_dir*.
    2. Pull Docker images required by the platform.
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

    # Prompt for missing tokens only if running interactively
    if gh_token is None and sys.stdin.isatty():
        gh_token = typer.prompt("GitHub token (leave blank if repo is public)", default="", hide_input=True) or None
    if docker_token is None and sys.stdin.isatty():
        docker_token = typer.prompt("Docker org access token (leave blank if images are public)", default="", hide_input=True) or None

    base_repo_url = "https://github.com/agentsystems/agent-platform-deployments.git"
    clone_repo_url = (base_repo_url.replace("https://", f"https://{gh_token}@") if gh_token else base_repo_url)
    typer.echo(f"Cloning {clone_repo_url} → {project_dir} (branch {branch})…")
    try:
        _run(["git", "clone", "--branch", branch, clone_repo_url, str(project_dir)])
    except typer.Exit:
        # If unauthenticated attempt failed and we didn't use a token, prompt (interactive) or abort.
        if gh_token is None and sys.stdin.isatty():
            gh_token = typer.prompt("Clone failed – provide GitHub token", hide_input=True)
            clone_repo_url = base_repo_url.replace("https://", f"https://{gh_token}@")
            _run(["git", "clone", "--branch", branch, clone_repo_url, str(project_dir)])
        else:
            raise

    typer.echo("Clone complete. Pulling Docker images (this may take a while)…")
    _ensure_docker_installed()
    _docker_login_if_needed(docker_token)
    for img in _required_images():
        typer.echo(f"  → pulling {img}")
        try:
            _run(["docker", "pull", img])
        except typer.Exit:
            if docker_token is None and sys.stdin.isatty():
                docker_token = typer.prompt("Pull failed – provide Docker org token", hide_input=True)
                _docker_login_if_needed(docker_token)
                _run(["docker", "pull", img])
            else:
                raise

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
    org = "agentsystems"
    typer.echo("Logging into Docker Hub…")
    _run(["docker", "login", registry, "-u", org, "-p", token])


def _required_images() -> List[str]:
    # Central place to keep image list – update when the platform adds new components.
    return [
        "agentsystems/agent-control-plane:latest",
        "agentsystems/hello-world-agent:latest",
    ]


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
