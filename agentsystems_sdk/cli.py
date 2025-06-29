"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

import os
import pathlib
from dotenv import load_dotenv, set_key
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
import re
import shutil
import subprocess
import sys
import time
import itertools
from typing import List, Optional

# Load .env before Typer parses env-var options
dotenv_global = os.getenv("AGENTSYSTEMS_GLOBAL_ENV")
if dotenv_global:
    dotenv_global = os.path.expanduser(dotenv_global)
    if os.path.exists(dotenv_global):
        load_dotenv(dotenv_path=dotenv_global)
# Fallback to .env in current working directory (if any)
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
        default_name = "agent-platform-deployments"
        dir_input = typer.prompt("Directory to create", default=default_name)
        project_dir = pathlib.Path(dir_input)
        if not project_dir.is_absolute():
            project_dir = pathlib.Path.cwd() / project_dir

    project_dir = project_dir.expanduser()
    if project_dir.exists() and any(project_dir.iterdir()):
        typer.secho(f"Directory {project_dir} is not empty – aborting.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Prompt for missing tokens only if running interactively

    # ---------- Langfuse initial setup prompts ----------
    if sys.stdin.isatty():
        console.print("\n[bold cyan]Langfuse initial setup[/bold cyan]")
        import re, uuid
        org_name = typer.prompt("Organization name", default="ExampleOrg")
        org_id = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"
        project_id = "default"
        project_name = "Default"
        user_name = "Admin"
        while True:
            email = typer.prompt("Admin email")
            if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                break
            console.print("[red]Please enter a valid email address.[/red]")
        while True:
            password = typer.prompt("Admin password (min 8 chars)", hide_input=True)
            if len(password) >= 8:
                break
            console.print("[red]Password must be at least 8 characters.[/red]")
        pub_key = f"pk-lf-{uuid.uuid4()}"
        secret_key = f"sk-lf-{uuid.uuid4()}"
    else:
        import uuid
        org_name = "ExampleOrg"
        org_id = "org"
        project_id = "default"
        project_name = "Default"
        user_name = "Admin"
        email = ""
        password = ""
        pub_key = f"pk-lf-{uuid.uuid4()}"
        secret_key = f"sk-lf-{uuid.uuid4()}"
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

            # Remove remote origin to avoid accidental pushes to template repo
            _run(["git", "-C", str(project_dir), "remote", "remove", "origin"])

            # ---------- Write Langfuse .env ----------
            env_example = project_dir / ".env.example"
            env_file = project_dir / ".env"
            if env_example.exists() and not env_file.exists():
                shutil.copy(env_example, env_file)
                env_file = project_dir / ".env"
            else:
                env_file = env_file if env_file.exists() else env_example

            from dotenv import set_key as _sk
            for k, v in {
                "LANGFUSE_INIT_ORG_ID": org_id,
                "LANGFUSE_INIT_ORG_NAME": org_name,
                "LANGFUSE_INIT_PROJECT_ID": project_id,
                "LANGFUSE_INIT_PROJECT_NAME": project_name,
                "LANGFUSE_INIT_USER_NAME": user_name,
                "LANGFUSE_INIT_USER_EMAIL": email,
                "LANGFUSE_INIT_USER_PASSWORD": password,
                "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": pub_key,
                "LANGFUSE_INIT_PROJECT_SECRET_KEY": secret_key,
                "LANGFUSE_PUBLIC_KEY": pub_key,
                "LANGFUSE_SECRET_KEY": secret_key,
            }.items():
                _sk(str(env_file), k, f'"{v}"', quote_mode="never")
            console.print("[green]✓ .env configured.[/green]")

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




    env_example = project_dir / ".env.example"
    env_file = project_dir / ".env"
    if env_example.exists() and not env_file.exists():
        shutil.copy(env_example, env_file)
        env_file = project_dir / ".env"
    else:
        env_file = env_file if env_file.exists() else env_example



    # ---------- Completion message ----------
    display_dir = project_dir.name
    next_steps = (
        f"✅ Initialization complete!\n\n"
        f"Next steps:\n"
        f"  1. cd {display_dir}\n"
        f"  2. Review .env and adjust if needed.\n"
        f"  3. Run: agentsystems up\n"
    )
    console.print(Panel.fit(next_steps, border_style="green"))


@app.command()
def up(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    detach: bool = typer.Option(True, '--detach/--foreground', '-d', help="Run containers in background (default) or stream logs in foreground"),
    fresh: bool = typer.Option(False, '--fresh', help="docker compose down -v before starting"),
    wait_ready: bool = typer.Option(True, '--wait/--no-wait', help="After start, wait until gateway is ready (detached mode only)"),
    no_langfuse: bool = typer.Option(False, '--no-langfuse', help="Disable Langfuse tracing stack"),
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

    # Build compose arguments (core + optional Langfuse stack)
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)

    # Require .env unless user supplied --env-file
    env_path = project_dir / '.env'
    if not env_path.exists() and env_file is None:
        typer.secho("Missing .env file in project directory. Run `cp .env.example .env` and populate it before 'agentsystems up'.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with Progress(SpinnerColumn(style="cyan"), TextColumn("[bold]{task.description}"), console=console) as prog:
        if fresh:
            down_task = prog.add_task("Removing previous containers", total=None)
            _run(["docker", "compose", *compose_args, "down", "-v"])
            prog.update(down_task, completed=1)

        up_cmd = ["docker", "compose", *compose_args, "up"]
        if env_file:
            up_cmd.extend(["--env-file", str(env_file)])
        if detach:
            up_cmd.append("-d")

        prog.add_task("Starting services", total=None)
        _run(up_cmd)

        # After successful startup, clean up init vars in the env file so they don't confuse users
        target_env_path = env_file if env_file else env_path
        if target_env_path.exists():
            _cleanup_init_vars(target_env_path)

    # Wait for readiness
    if detach and wait_ready:
        _wait_for_gateway_ready(core_compose)

    console.print(Panel.fit("✅ [bold green]Platform is running![/bold green]", border_style="green"))


@app.command()
def down(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    volumes: bool = typer.Option(False, '--volumes', '-v', help="Remove named volumes (docker compose down -v)"),
    no_langfuse: bool = typer.Option(False, '--no-langfuse', help="Disable Langfuse tracing stack"),
    env_file: Optional[pathlib.Path] = typer.Option(None, '--env-file', help="Custom .env file passed to docker compose", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    """Stop the AgentSystems platform containers and optionally remove volumes."""
    console.print(Panel.fit("🛑 [bold cyan]AgentSystems Platform – down[/bold cyan]", border_style="bright_cyan"))
 
    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
 
    with Progress(SpinnerColumn(style="cyan"), TextColumn("[bold]{task.description}"), console=console) as prog:
        task = prog.add_task("Stopping services", total=None)
        down_cmd = ["docker", "compose", *compose_args, "down"]
        if volumes:
            _confirm_danger("remove Docker volumes")
            down_cmd.append("-v")
        if env_file:
            down_cmd.extend(["--env-file", str(env_file)])
        _run(down_cmd)
        prog.update(task, completed=1)
    console.print(Panel.fit("✅ [bold green]Platform stopped[/bold green]", border_style="green"))


@app.command()
def logs(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    service: Optional[str] = typer.Option(None, '--service', '-s', help="Filter logs to a single service"),
    no_langfuse: bool = typer.Option(False, '--no-langfuse', help="Disable Langfuse tracing stack"),
    tail: int = typer.Option(100, '--tail', help="Number of recent lines to show"),
    since: Optional[str] = typer.Option(None, '--since', help="Show logs since timestamp or relative e.g. 10m"),
    follow: bool = typer.Option(True, '--follow/--no-follow', help="Stream logs (default on)"),
) -> None:
    """Stream container logs (docker compose logs)."""
    console.print(Panel.fit("📜 [bold cyan]AgentSystems Platform – logs[/bold cyan]", border_style="bright_cyan"))

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    candidates = [
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
    ]
    compose_file: pathlib.Path | None = next((p for p in candidates if p.exists()), None)
    if compose_file is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
    cmd = ["docker", "compose", *compose_args, "logs"]
    if follow:
        cmd.append("--follow")
    if tail is not None:
        cmd.extend(["--tail", str(tail)])
    if since:
        cmd.extend(["--since", since])
    if service:
        cmd.append(service)

    _run(cmd)


@app.command()
def status(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    service: Optional[str] = typer.Option(None, '--service', '-s', help="Show status for a single service"),
    no_langfuse: bool = typer.Option(False, '--no-langfuse', help="Disable Langfuse tracing stack"),
) -> None:
    """Show running containers and their state (docker compose ps)."""

    console.print(Panel.fit("🩺 [bold cyan]AgentSystems Platform – status[/bold cyan]", border_style="bright_cyan"))

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    candidates = [
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
    ]
    compose_file: pathlib.Path | None = next((p for p in candidates if p.exists()), None)
    if compose_file is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
    cmd = ["docker", "compose", *compose_args, "ps"]
    if service:
        cmd.append(service)

    _run(cmd)


@app.command()
def restart(
    project_dir: pathlib.Path = typer.Argument('.', exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help="Path to an agent-platform-deployments checkout"),
    volumes: bool = typer.Option(False, '--volumes', '-v', help="Remove named volumes during restart"),
    foreground: bool = typer.Option(False, '--foreground/--detach', help="Run in foreground (stream logs) or detach (default)"),
    no_langfuse: bool = typer.Option(False, '--no-langfuse', help="Disable Langfuse tracing stack"),
    wait_ready: bool = typer.Option(True, '--wait/--no-wait', help="Wait until gateway is ready (detached mode only)"),
    env_file: Optional[pathlib.Path] = typer.Option(None, '--env-file', help="Custom .env file passed to docker compose", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    """Restart the platform (down then up)."""
    console.print(Panel.fit("🔄 [bold cyan]AgentSystems Platform – restart[/bold cyan]", border_style="bright_cyan"))

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    candidates = [
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
    ]
    compose_file: pathlib.Path | None = next((p for p in candidates if p.exists()), None)
    if compose_file is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    core_compose, compose_args = _compose_args(project_dir, no_langfuse)

    # Ensure .env present unless --env-file supplied
    env_path = project_dir / '.env'
    if not env_path.exists() and env_file is None:
        typer.secho("Missing .env file in project directory. Run `cp .env.example .env` and populate it before 'agentsystems restart'.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # down
    down_cmd = ["docker", "compose", *compose_args, "down"]
    if volumes:
        _confirm_danger("remove Docker volumes")
        down_cmd.append("-v")
    if env_file:
        down_cmd.extend(["--env-file", str(env_file)])
    _run(down_cmd)

    # up
    up_cmd = ["docker", "compose", *compose_args, "up"]
    if not foreground:
        up_cmd.append("-d")
    if env_file:
        up_cmd.extend(["--env-file", str(env_file)])
    _run(up_cmd)

    if not foreground and wait_ready:
        _wait_for_gateway_ready(core_compose)

    console.print(Panel.fit("✅ [bold green]Platform restarted[/bold green]", border_style="green"))


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

def _configure_env(env_path: pathlib.Path) -> None:
    """Interactively configure the .env file copied from .env.example."""
    import re

    console.print(Panel.fit("🔑 [bold cyan]Configure Langfuse environment[/bold cyan]", border_style="bright_cyan"))

    # Organization
    org_name = typer.prompt("Organization name", default="ExampleOrg")
    org_id = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"

    # Project defaults
    project_id = "default"
    project_name = "Default"

    # User defaults and prompts
    user_name = "Admin"

    # Email prompt with validation
    while True:
        email = typer.prompt("Admin email")
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            break
        console.print("[red]Please enter a valid email address.[/red]")

    # Password prompt with minimum length check
    while True:
        password = typer.prompt("Admin password (min 8 chars)", hide_input=True)
        if len(password) >= 8:
            break
        console.print("[red]Password must be at least 8 characters.[/red]")

    # Key generation (UUID4 to match pk/sk-lf-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
    pub_key = f"pk-lf-{uuid.uuid4()}"
    secret_key = f"sk-lf-{uuid.uuid4()}"

    # Helper to write without quotes
    def _set(k: str, v: str) -> None:
        # Write value wrapped in double quotes
        set_key(str(env_path), k, f'"{v}"', quote_mode="never")

    # Write values to .env (overwrite placeholders)
    _set("LANGFUSE_INIT_ORG_ID", org_id)
    _set("LANGFUSE_INIT_ORG_NAME", org_name)
    _set("LANGFUSE_INIT_PROJECT_ID", project_id)
    _set("LANGFUSE_INIT_PROJECT_NAME", project_name)
    _set("LANGFUSE_INIT_USER_NAME", user_name)
    _set("LANGFUSE_INIT_USER_EMAIL", email)
    _set("LANGFUSE_INIT_USER_PASSWORD", password)
    _set("LANGFUSE_INIT_PROJECT_PUBLIC_KEY", pub_key)
    _set("LANGFUSE_PUBLIC_KEY", pub_key)
    _set("LANGFUSE_INIT_PROJECT_SECRET_KEY", secret_key)
    _set("LANGFUSE_SECRET_KEY", secret_key)

    console.print("[green]✓ .env configured (init vars remain).[/green]")
    return

    # ------------------------------------------------------------------
    # Re-format: keep runtime vars at top, move init vars (commented) to
    # the bottom with a notice so the user can still reference them.
    # ------------------------------------------------------------------
    try:
        lines = env_path.read_text().splitlines()
    except Exception as exc:
        console.print(f"[yellow]Could not reformat .env: {exc}[/yellow]")
    else:
        init_lines = []
        other_lines = []
        for ln in lines:
            # strip leading comment when matching
            stripped = ln.lstrip("# ")
            if stripped.startswith("LANGFUSE_INIT_"):
                # store original line (uncommented) for accuracy
                key, _, val = stripped.partition("=")
                init_lines.append(f"{key}={val}")
            else:
                other_lines.append(ln)

        if init_lines:
            notice = (
                "# --- Langfuse initialization values (no longer used after first start) ---\n"
                "# You can remove these lines or keep them for reference.\n"
            )
            commented_inits = [f"# {l}" for l in init_lines]
            new_content = "\n".join(other_lines + ["", notice] + commented_inits) + "\n"
            env_path.write_text(new_content)

    console.print("[green]✓ .env configured.[/green]")


def _cleanup_init_vars(env_path: pathlib.Path) -> None:
    """Comment out LANGFUSE_INIT_* variables in the given .env file.
    After first startup they are no longer required but useful for reference.
    Keeps runtime vars at top, appends commented init vars to bottom with a notice."""
    try:
        lines = env_path.read_text().splitlines()
    except Exception:
        return

    init_lines: list[str] = []
    other_lines: list[str] = []
    for ln in lines:
        stripped = ln.lstrip("# ")
        if stripped.startswith("LANGFUSE_INIT_"):
            key, _, val = stripped.partition("=")
            init_lines.append(f"{key}={val}")
        else:
            other_lines.append(ln)

    if init_lines:
        notice = (
            "# --- Langfuse initialization values (no longer used after first start) ---\n"
            "# You can remove these lines or keep them for reference.\n"
        )
        commented = [f"# {l}" for l in init_lines]
        new_content = "\n".join(other_lines + ["", notice] + commented) + "\n"
        env_path.write_text(new_content)


def _compose_args(project_dir: pathlib.Path, no_langfuse: bool) -> tuple[pathlib.Path, list[str]]:
    """Return (core_compose_path, list_of_-f_args) respecting *no_langfuse*."""
    # core compose – prefer explicit local file
    core_candidates = [
        project_dir / 'compose' / 'local' / 'docker-compose.yml',
        project_dir / 'docker-compose.yml',
        project_dir / 'docker-compose.yaml',
    ]
    core: pathlib.Path | None = next((p for p in core_candidates if p.exists()), None)
    if core is None:
        typer.secho("docker-compose.yml not found – pass the project directory (or run inside it)", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    args = ["-f", str(core)]

    if not no_langfuse:
        lf = project_dir / 'compose' / 'langfuse' / 'docker-compose.yml'
        if lf.exists():
            args.extend(["-f", str(lf)])
    return core, args


def _wait_for_gateway_ready(compose_file: pathlib.Path, service: str = "gateway", timeout: int = 120) -> None:
    """Show spinner while tailing logs until the gateway reports readiness."""
    cmd = ["docker", "compose", "-f", str(compose_file), "logs", "--no-color", "-f", service]
    ready_patterns = [
        re.compile(r"Application startup complete", re.I),
        re.compile(r"Uvicorn running", re.I),
    ]

    start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    with Progress(SpinnerColumn(style="cyan"), TextColumn("[bold cyan]Waiting for gateway…[/bold cyan]"), console=console, transient=True) as prog:
        task = prog.add_task("wait", total=None)
        try:
            for line in proc.stdout:  # type: ignore[attr-defined]
                if any(p.search(line) for p in ready_patterns):
                    proc.terminate()
                    break
                if time.time() - start > timeout:
                    console.print("[yellow]Gateway readiness timeout reached – continuing anyway.[/yellow]")
                    proc.terminate()
                    break
        except Exception:
            proc.terminate()
        finally:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    console.print("[green]Gateway ready![/green]")


def _confirm_danger(action: str) -> None:
    """Prompt the user to confirm a destructive *action* (like erasing volumes)."""
    if not typer.confirm(f"⚠️  This will {action} and data may be lost. Continue?", default=False):
        raise typer.Exit(code=1)

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
