"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

import os
import pathlib
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
import re
import shutil
import subprocess
import sys
from typing import List, Optional

# Load .env before Typer parses env-var options
load_dotenv()

import typer

console = Console()
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
    # ---------- UI banner ----------
    console.print(Panel.fit("🚀 [bold cyan]AgentSystems SDK[/bold cyan] – initialization", border_style="bright_cyan"))

    # ---------- Progress ----------
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(style="bright_magenta"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        clone_task = progress.add_task("Cloning template repo", total=None)
        display_url = re.sub(r"https://[^@]+@", "https://", clone_repo_url)
        try:
            _run(["git", "clone", "--branch", branch, clone_repo_url, str(project_dir)])
        finally:
            progress.update(clone_task, completed=1)

        progress.add_task("Checking Docker", total=None)
        _ensure_docker_installed()

        if docker_token:
            progress.add_task("Logging into Docker Hub", total=None)
            _docker_login_if_needed(docker_token)

        pull_task = progress.add_task("Pulling Docker images", total=len(_required_images()))
        for img in _required_images():
            progress.update(pull_task, description=f"Pulling {img}")
            try:
                _run(["docker", "pull", img])
            except typer.Exit:
                if docker_token is None and sys.stdin.isatty():
                    docker_token = typer.prompt("Pull failed – provide Docker org token", hide_input=True)
                    _docker_login_if_needed(docker_token)
                    _run(["docker", "pull", img])
                else:
                    raise
            progress.advance(pull_task)



    # ---------- Completion message ----------
    console.print(Panel.fit(f"✅ [bold green]Initialization complete![/bold green]\n[white]Navigate to[/white] [bold]{project_dir}[/bold]", border_style="green"))


@app.command()
def up(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    detach: bool = typer.Option(True, '--detach/--foreground', '-d', help="Run containers in background (default) or stream logs in foreground"),
    fresh: bool = typer.Option(False, '--fresh', help="docker compose down -v before starting"),
    env_file: Optional[pathlib.Path] = typer.Option(None, '--env-file', help="Custom .env file passed to docker compose", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    docker_token: str | None = typer.Option(None, '--docker-token', envvar='DOCKER_OAT', help="Docker Hub Org Access Token for private images"),
) -> None:
    """Start the full AgentSystems platform via docker compose.

    Equivalent to the legacy `make up`. Provides convenience flags and polished output.
    """
    console.print(Panel.fit("🐳 [bold cyan]AgentSystems Platform – up[/bold cyan]", border_style="bright_cyan"))

    _ensure_docker_installed()
    if docker_token:
        _docker_login_if_needed(docker_token)

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Detect compose file
    candidates = [
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
    ]
    compose_file: pathlib.Path | None = next((p for p in candidates if p.exists()), None)
    if compose_file is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)



    with Progress(SpinnerColumn(style="cyan"), TextColumn("[bold]{task.description}"), console=console) as prog:
        if fresh:
            down_task = prog.add_task("Removing previous containers", total=None)
            _run(["docker", "compose", "-f", str(compose_file), "down", "-v"])
            prog.update(down_task, completed=1)

        up_cmd = ["docker", "compose", "-f", str(compose_file), "up"]
        if env_file:
            up_cmd.extend(["--env-file", str(env_file)])
        if detach:
            up_cmd.append("-d")

        prog.add_task("Starting services", total=None)
        _run(up_cmd)

    console.print(Panel.fit("✅ [bold green]Platform is running![/bold green]", border_style="green"))


@app.command()
def down(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    volumes: bool = typer.Option(False, '--volumes', '-v', help="Remove named volumes (docker compose down -v)"),
    env_file: Optional[pathlib.Path] = typer.Option(None, '--env-file', help="Custom .env file passed to docker compose", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    """Stop the AgentSystems platform containers and optionally remove volumes."""
    console.print(Panel.fit("🛑 [bold cyan]AgentSystems Platform – down[/bold cyan]", border_style="bright_cyan"))
 
    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    # Detect compose file (same heuristics as `up`)
    candidates = [
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
    ]
    compose_file: pathlib.Path | None = next((p for p in candidates if p.exists()), None)
    if compose_file is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    with Progress(SpinnerColumn(style="cyan"), TextColumn("[bold]{task.description}"), console=console) as prog:
        task = prog.add_task("Stopping services", total=None)
        down_cmd = ["docker", "compose", "-f", str(compose_file), "down"]
        if volumes:
            down_cmd.append("-v")
        if env_file:
            down_cmd.extend(["--env-file", str(env_file)])
        _run(down_cmd)
        prog.update(task, completed=1)
    console.print(Panel.fit("✅ [bold green]Platform stopped[/bold green]", border_style="green"))


@app.command()
def info() -> None:
    """Display environment and SDK diagnostic information."""
    import platform, sys, shutil

    console.print(Panel.fit("ℹ️  [bold cyan]AgentSystems SDK info[/bold cyan]", border_style="bright_cyan"))

    rows = [
        ("SDK version", _metadata.version("agentsystems-sdk")),
        ("Python", sys.version.split()[0]),
        ("Platform", platform.platform()),
    ]
    docker_path = shutil.which("docker")
    if docker_path:
        try:
            docker_ver = subprocess.check_output(["docker", "--version"], text=True).strip()
        except Exception:
            docker_ver = "installed (version unknown)"
    else:
        docker_ver = "not found"
    rows.append(("Docker", docker_ver))

    table_lines = "\n".join(f"[bold]{k:12}[/bold] {v}" for k, v in rows)
    console.print(table_lines)


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
    """Login to Docker Hub using an isolated config dir to sidestep credential helpers.

    Some environments (notably macOS with Docker Desktop) configure a credential helper
    that writes to the OS key-chain, which can fail in headless shells. We point
    DOCKER_CONFIG at a throw-away directory so `docker login` keeps credentials in a
    plain JSON file instead.
    """
    if not token:
        return

    import tempfile

    registry = "docker.io"
    org = "agentsystems"
    typer.echo("Logging into Docker Hub…")
    with tempfile.TemporaryDirectory(prefix="agentsystems-docker-config-") as tmp_cfg:
        env = os.environ.copy()
        env["DOCKER_CONFIG"] = tmp_cfg
        try:
            subprocess.run(
                ["docker", "login", registry, "-u", org, "--password-stdin"],
                input=f"{token}\n".encode(),
                check=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            typer.secho("Docker login failed", fg=typer.colors.RED)
            raise typer.Exit(exc.returncode) from exc


def _required_images() -> List[str]:
    # Central place to keep image list – update when the platform adds new components.
    return [
        "agentsystems/agent-control-plane:latest",
        "agentsystems/hello-world-agent:latest",
    ]


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
