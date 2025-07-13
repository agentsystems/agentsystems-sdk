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
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
import re
import shutil
import docker
import subprocess
import sys
import time
from typing import List, Optional, Dict

from agentsystems_sdk.config import Config  # new

import typer

# Load .env before Typer parses env-var options
dotenv_global = os.getenv("AGENTSYSTEMS_GLOBAL_ENV")
if dotenv_global:
    dotenv_global = os.path.expanduser(dotenv_global)
    if os.path.exists(dotenv_global):
        load_dotenv(dotenv_path=dotenv_global)
# Fallback to .env in current working directory (if any)
load_dotenv()


console = Console()

# Detect Docker Compose CLI once at import time --------------------------------
if shutil.which("docker-compose"):
    _COMPOSE_BIN: list[str] = ["docker-compose"]
else:
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        _COMPOSE_BIN = ["docker", "compose"]
    except Exception:
        _COMPOSE_BIN = []


# ---------------------------------------------------------------------------
# Helper functions for running subprocesses with proper error handling
# ---------------------------------------------------------------------------


def _run(cmd: List[str]) -> None:
    """Run *cmd* inheriting the current environment.

    Exits the Typer application with the same exit code if the command fails.
    """
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        typer.secho(f"Command failed: {' '.join(cmd)}", fg=typer.colors.RED)
        raise typer.Exit(exc.returncode) from exc


def _run_env(cmd: List[str], env: dict[str, str]) -> None:
    """Run *cmd* with a custom *env* mapping and abort on failure."""
    try:
        subprocess.check_call(cmd, env=env)
    except subprocess.CalledProcessError as exc:
        typer.secho(f"Command failed: {' '.join(cmd)}", fg=typer.colors.RED)
        raise typer.Exit(exc.returncode) from exc


# Additional helper utilities --------------------------------------------------


def _ensure_docker_installed() -> None:
    """Exit if Docker CLI is not found."""
    if shutil.which("docker") is None:
        typer.secho(
            "Docker CLI not found. Please install Docker Desktop and retry.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def _docker_login_if_needed(token: str | None) -> None:
    """Login to Docker Hub using an isolated config dir when *token* is provided."""
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


def _ensure_agents_net() -> None:
    """Create the shared Docker network 'agents-net' if absent."""
    try:
        subprocess.run(
            ["docker", "network", "inspect", "agents-net"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.check_call(["docker", "network", "create", "agents-net"])


# ---------------------------------------------------------------------------
# Additional platform helper functions that were missing after refactor
# ---------------------------------------------------------------------------


def _cleanup_init_vars(env_path: pathlib.Path) -> None:
    """Comment-out one-time LANGFUSE_INIT_* vars after first successful start."""
    lines = env_path.read_text().splitlines()
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
        commented = [f"# {line}" for line in init_lines]
        new_content = "\n".join(other_lines + ["", notice] + commented) + "\n"
        env_path.write_text(new_content)


def _compose_args(
    project_dir: pathlib.Path, no_langfuse: bool
) -> tuple[pathlib.Path, list[str]]:
    """Return (core compose file, -f arg list) honoring *no_langfuse*."""
    core_candidates = [
        project_dir / "compose" / "local" / "docker-compose.yml",
        project_dir / "docker-compose.yml",
        project_dir / "docker-compose.yaml",
    ]
    core = next((p for p in core_candidates if p.exists()), None)
    if core is None:
        typer.secho(
            "docker-compose.yml not found – pass the project directory (or run inside it)",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    args: list[str] = ["-f", str(core)]
    if not no_langfuse:
        lf = project_dir / "compose" / "langfuse" / "docker-compose.yml"
        if lf.exists():
            args.extend(["-f", str(lf)])
    return core, args


def _wait_for_gateway_ready(
    compose_file: pathlib.Path, service: str = "gateway", timeout: int = 120
) -> None:
    """Tail logs until the gateway reports readiness or *timeout* seconds."""
    if not _COMPOSE_BIN:
        typer.secho(
            "Docker Compose not found (plugin or standalone). Install it and retry.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    cmd = [*_COMPOSE_BIN, "-f", str(compose_file), "logs", "--no-color", "-f", service]
    ready_patterns = [
        re.compile(r"Application startup complete", re.I),
        re.compile(r"Uvicorn running", re.I),
    ]
    start = time.time()
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]Waiting for gateway…[/bold cyan]"),
        console=console,
        transient=True,
    ) as prog:
        prog.add_task("wait", total=None)
        try:
            for line in proc.stdout:  # type: ignore[attr-defined]
                if any(p.search(line) for p in ready_patterns):
                    proc.terminate()
                    break
                if time.time() - start > timeout:
                    console.print(
                        "[yellow]Gateway readiness timeout reached – continuing anyway.[/yellow]"
                    )
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


# ---------------------------------------------------------------------------

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
    project_dir: Optional[pathlib.Path] = typer.Argument(
        None,
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
    ),
    branch: str = typer.Option("main", help="Branch to clone"),
    gh_token: str | None = typer.Option(
        None,
        "--gh-token",
        envvar="GITHUB_TOKEN",
        help="GitHub Personal Access Token for private template repo",
    ),
    docker_token: str | None = typer.Option(
        None,
        "--docker-token",
        envvar="DOCKER_OAT",
        help="Docker Hub Org Access Token for private images",
    ),
):
    """Clone the agent deployment template and pull required Docker images.

    Steps:
    1. Clone the `agent-platform-deployments` template repo into *project_dir*.
    2. Pull Docker images required by the platform.
    """
    # Determine target directory
    if project_dir is None:
        if not sys.stdin.isatty():
            typer.secho(
                "TARGET_DIR argument required when running non-interactively.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        default_name = "agent-platform-deployments"
        dir_input = typer.prompt("Directory to create", default=default_name)
        project_dir = pathlib.Path(dir_input)
        if not project_dir.is_absolute():
            project_dir = pathlib.Path.cwd() / project_dir

    project_dir = project_dir.expanduser()
    if project_dir.exists() and any(project_dir.iterdir()):
        typer.secho(
            f"Directory {project_dir} is not empty – aborting.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    # Prompt for missing tokens only if running interactively

    # ---------- Langfuse initial setup prompts ----------
    if sys.stdin.isatty():
        console.print("\n[bold cyan]Langfuse initial setup[/bold cyan]")
        import re
        import uuid

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
        gh_token = (
            typer.prompt(
                "GitHub token (leave blank if repo is public)",
                default="",
                hide_input=True,
            )
            or None
        )
    if docker_token is None and sys.stdin.isatty():
        docker_token = (
            typer.prompt(
                "Docker org access token (leave blank if images are public)",
                default="",
                hide_input=True,
            )
            or None
        )

    base_repo_url = "https://github.com/agentsystems/agent-platform-deployments.git"
    clone_repo_url = (
        base_repo_url.replace("https://", f"https://{gh_token}@")
        if gh_token
        else base_repo_url
    )
    # ---------- UI banner ----------
    console.print(
        Panel.fit(
            "🚀 [bold cyan]AgentSystems SDK[/bold cyan] – initialization",
            border_style="bright_cyan",
        )
    )

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
        _display_url = re.sub(r"https://[^@]+@", "https://", clone_repo_url)
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

            cfg_pairs = {
                "LANGFUSE_INIT_ORG_ID": org_id,
                "LANGFUSE_INIT_ORG_NAME": org_name,
                "LANGFUSE_INIT_PROJECT_ID": project_id,
                "LANGFUSE_INIT_PROJECT_NAME": project_name,
                "LANGFUSE_INIT_USER_NAME": user_name,
                "LANGFUSE_INIT_USER_EMAIL": email,
                "LANGFUSE_INIT_USER_PASSWORD": password,
                "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": pub_key,
                "LANGFUSE_INIT_PROJECT_SECRET_KEY": secret_key,
                # Runtime vars (must be *unquoted* for Docker)
                "LANGFUSE_HOST": "http://langfuse-web:3000",
                "LANGFUSE_PUBLIC_KEY": pub_key,
                "LANGFUSE_SECRET_KEY": secret_key,
            }

            for k, v in cfg_pairs.items():
                # Quote only the one-shot INIT vars; runtime vars stay raw
                value_to_write = f'"{v}"' if k.startswith("LANGFUSE_INIT_") else str(v)
                _sk(str(env_file), k, value_to_write, quote_mode="never")
            console.print("[green]✓ .env configured.[/green]")

        progress.add_task("Checking Docker", total=None)
        _ensure_docker_installed()

        if docker_token:
            progress.add_task("Logging into Docker Hub", total=None)
            _docker_login_if_needed(docker_token)

        pull_task = progress.add_task(
            "Pulling Docker images", total=len(_required_images())
        )
        for img in _required_images():
            progress.update(pull_task, description=f"Pulling {img}")
            try:
                _run(["docker", "pull", img])
            except typer.Exit:
                if docker_token is None and sys.stdin.isatty():
                    docker_token = typer.prompt(
                        "Pull failed – provide Docker org token", hide_input=True
                    )
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
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--foreground",
        "-d",
        help="Run containers in background (default) or stream logs in foreground",
    ),
    fresh: bool = typer.Option(
        False, "--fresh", help="docker compose down -v before starting"
    ),
    wait_ready: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="After start, wait until gateway is ready (detached mode only)",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse tracing stack"
    ),
    env_file: Optional[pathlib.Path] = typer.Option(
        None,
        "--env-file",
        help="Custom .env file passed to docker compose",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Start the full AgentSystems platform via docker compose.

    Equivalent to the legacy `make up`. Provides convenience flags and polished output.
    """
    console.print(
        Panel.fit(
            "🐳 [bold cyan]AgentSystems Platform – up[/bold cyan]",
            border_style="bright_cyan",
        )
    )

    _ensure_docker_installed()

    # --------------------------------------------------
    # Use isolated Docker config for the entire session so global Docker login
    # state never interferes with pulls/logins.
    import tempfile

    isolated_cfg = tempfile.TemporaryDirectory(prefix="agentsystems-docker-config-")
    env_base = os.environ.copy()
    env_base["DOCKER_CONFIG"] = isolated_cfg.name

    # .env gets loaded later – keep env_base in sync so any newly loaded vars
    # such as DOCKERHUB_USER/TOKEN are available to subprocesses.
    def _sync_env_base() -> None:
        env_base.update(os.environ)

    # Optional upfront login to docker.io so that docker compose can pull core
    # images (control-plane, hello-world) before marketplace logic runs.
    hub_user = os.getenv("DOCKERHUB_USER")
    hub_token = os.getenv("DOCKERHUB_TOKEN")
    if hub_user and hub_token:
        console.print(
            "[cyan]⇒ logging into docker.io (basic auth via DOCKERHUB_USER/DOCKERHUB_TOKEN) for compose pull[/cyan]"
        )
        try:
            subprocess.run(
                ["docker", "login", "docker.io", "-u", hub_user, "--password-stdin"],
                input=f"{hub_token}\n".encode(),
                check=True,
                env=env_base,
            )
        except subprocess.CalledProcessError:
            console.print(
                "[red]Docker login failed – check DOCKERHUB_USER/DOCKERHUB_TOKEN.[/red]"
            )
            raise typer.Exit(code=1)

    # --------------------------------------------------
    # Load agentsystems-config.yml if present
    cfg_path = project_dir / "agentsystems-config.yml"
    cfg: Config | None = None
    if cfg_path.exists():
        try:
            cfg = Config(cfg_path)
            console.print(
                f"[cyan]✓ Loaded config ({len(cfg.agents)} agents, {len(cfg.enabled_registries())} registries).[/cyan]"
            )
        except Exception as e:
            typer.secho(f"Error parsing {cfg_path}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    # --------------------------------------------------

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Detect compose CLI (plugin vs standalone)

    # Build compose arguments (core + optional Langfuse stack)
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)

    # Require .env unless user supplied --env-file
    env_path = project_dir / ".env"
    if not env_path.exists() and env_file is None:
        typer.secho(
            "Missing .env file in project directory. Run `cp .env.example .env` and populate it before 'agentsystems up'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        console=console,
    ) as prog:
        if fresh:
            down_task = prog.add_task("Removing previous containers", total=None)
            _run_env([*_COMPOSE_BIN, *compose_args, "down", "-v"], env_base)
            prog.update(down_task, completed=1)

        up_cmd = [*_COMPOSE_BIN, *compose_args, "up"]
        if env_file:
            up_cmd.extend(["--env-file", str(env_file)])
        if detach:
            up_cmd.append("-d")

        prog.add_task("Starting services", total=None)
        _run_env(up_cmd, env_base)

        # After successful startup, clean up init vars in the env file so they don't confuse users
        target_env_path = env_file if env_file else env_path
        if target_env_path.exists():
            _cleanup_init_vars(target_env_path)
            # Ensure variables like DOCKERHUB_USER/TOKEN are available for CLI itself
            load_dotenv(dotenv_path=target_env_path, override=False)
            _sync_env_base()

    # --------------------------------------------------
    # If config specified agents, ensure registries are logged in & images pulled, then run containers
    if cfg:
        _setup_agents_from_config(cfg, project_dir)

    # Wait for readiness
    # Restart gateway so it picks up any newly started agents (routing table reload)
    console.print("[cyan]↻ restarting gateway to reload agent routes…[/cyan]")
    try:
        _run_env([*_COMPOSE_BIN, *compose_args, "restart", "gateway"], env_base)
    except Exception:
        pass

    if detach and wait_ready:
        _wait_for_gateway_ready(core_compose)

    console.print(
        Panel.fit(
            "✅ [bold green]Platform is running![/bold green]", border_style="green"
        )
    )

    # Temporary Docker config directory is cleaned up when object is GC'd but
    # we explicitly clean to avoid stray dirs
    isolated_cfg.cleanup()


# Marketplace helpers -------------------------------------------------------


def _setup_agents_from_config(cfg: Config, project_dir: pathlib.Path) -> None:
    """Login to each enabled registry in an isolated config & start agents.

    We always log in using credentials specified in `.env` / env-vars, never
    relying on the user's global Docker credentials.  A temporary DOCKER_CONFIG
    directory keeps this session separate so we don't clobber or depend on the
    operator's normal login state.
    """
    import tempfile

    client = docker.from_env()
    _ensure_agents_net()

    # --- Pull images per registry using isolated DOCKER_CONFIG dirs ------
    # Build mapping of registry key -> list[Agent]
    from collections import defaultdict

    agents_by_reg: Dict[str, List] = defaultdict(list)
    for agent in cfg.agents:
        agents_by_reg[agent.registry].append(agent)

    def _image_exists(ref: str, env: dict) -> bool:  # type: ignore[arg-type]
        """Return True if *ref* image is already present (using given env)."""
        return (
            subprocess.run(
                ["docker", "image", "inspect", ref],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            ).returncode
            == 0
        )

    for reg_key, agents_list in agents_by_reg.items():
        reg = cfg.registries.get(reg_key)
        if not reg or not reg.enabled:
            continue  # skip disabled registries

        # Create a fresh Docker config dir so credentials don't clobber
        with tempfile.TemporaryDirectory(
            prefix="agentsystems-docker-config-"
        ) as tmp_cfg:
            env = os.environ.copy()
            env["DOCKER_CONFIG"] = tmp_cfg

            # ---- Login --------------------------------------------------
            method = reg.login_method()
            if method == "none":
                console.print(f"[cyan]ℹ︎ {reg.url}: no auth required[/cyan]")
            elif method == "basic":
                user = os.getenv(reg.username_env() or "")
                pw = os.getenv(reg.password_env() or "")
                if not (user and pw):
                    not_present = [
                        a.image for a in agents_list if not _image_exists(a.image, env)
                    ]
                    if not not_present:
                        console.print(
                            f"[yellow]⚠︎ Skipping login to {reg.url} – credentials missing but images already cached.[/yellow]"
                        )
                    else:
                        console.print(
                            f"[red]✗ {reg.url}: missing {reg.username_env()}/{reg.password_env()} and images not cached.[/red]"
                        )
                        raise typer.Exit(code=1)
                else:
                    console.print(
                        f"[cyan]⇒ logging into {reg.url} (basic auth via {reg.username_env()}/{reg.password_env()})[/cyan]"
                    )
                    subprocess.run(
                        ["docker", "login", reg.url, "-u", user, "--password-stdin"],
                        input=f"{pw}\n".encode(),
                        check=True,
                        env=env,
                    )
            elif method in {"bearer", "token"}:
                token = os.getenv(reg.token_env() or "")
                if not token:
                    console.print(
                        f"[red]✗ {reg.url}: missing {reg.token_env()} in environment.[/red]"
                    )
                    raise typer.Exit(code=1)
                console.print(
                    f"[cyan]⇒ logging into {reg.url} (token via {reg.token_env()})[/cyan]"
                )
                subprocess.run(
                    [
                        "docker",
                        "login",
                        reg.url,
                        "--username",
                        "oauth2",
                        "--password-stdin",
                    ],
                    input=f"{token}\n".encode(),
                    check=True,
                    env=env,
                )
            else:
                console.print(
                    f"[red]✗ {reg.url}: unknown auth method '{method}'.[/red]"
                )
                raise typer.Exit(code=1)

            # ---- Pull images -------------------------------------------
            for agent in agents_list:
                img = agent.image
                alt_ref = img.split("/", 1)[1] if "/" in img else img
                if _image_exists(img, env) or _image_exists(alt_ref, env):
                    console.print(f"[green]✓ {img} already present.[/green]")
                    continue
                console.print(f"[cyan]⇣ pulling {img}…[/cyan]")
                subprocess.run(["docker", "pull", img], check=True, env=env)

    # Reset env_base for container startup (credentials no longer needed)
    env_base = os.environ.copy()

    # 3. Start containers
    env_file_path = project_dir / ".env"
    if not env_file_path.exists():
        console.print(
            "[yellow]No .env file found – agents will run without extra environment variables.[/yellow]"
        )

    for agent in cfg.agents:
        # Derive service/container name from image reference (basename without tag)
        image_ref = agent.image
        service_name = image_ref.rsplit("/", 1)[-1].split(":", 1)[0]
        cname = service_name
        # Remove legacy-named container if it exists (agent-<name>)
        legacy_name = f"agent-{agent.name}"
        if legacy_name != cname:
            try:
                legacy = client.containers.get(legacy_name)
                console.print(
                    f"[yellow]Removing legacy container {legacy_name}…[/yellow]"
                )
                legacy.remove(force=True)
            except docker.errors.NotFound:
                pass

        try:
            client.containers.get(cname)
            console.print(f"[green]✓ {cname} already running.[/green]")
            if not _wait_for_agent_healthy(client, cname):
                console.print(f"[red]✗ {cname} failed health check (timeout).[/red]")
            continue
        except docker.errors.NotFound:
            pass

        labels = {
            "agent.enabled": "true",
            "com.docker.compose.project": "local",
            "com.docker.compose.service": service_name,
        }
        # agent-specific labels override defaults
        labels.update(agent.labels)
        labels.setdefault("agent.port", labels.get("agent.port", "8000"))

        expose_ports = agent.overrides.get("expose", [labels["agent.port"]])
        port = str(expose_ports[0])

        cmd = [
            "docker",
            "run",
            "-d",
            "--restart",
            "unless-stopped",
            "--name",
            cname,
            "--network",
            "agents-net",
            "--env-file",
            str(env_file_path) if env_file_path.exists() else "/dev/null",
        ]
        # labels
        for k, v in labels.items():
            cmd.extend(["--label", f"{k}={v}"])
        # env overrides
        for k, v in agent.overrides.get("env", {}).items():
            cmd.extend(["--env", f"{k}={v}"])
        # port mapping (random host port)
        cmd.extend(["-p", port])
        # image
        cmd.append(agent.image)

        console.print(f"[cyan]▶ starting {cname} ({agent.image})…[/cyan]")
        subprocess.run(cmd, check=True, env=env_base)
        if _wait_for_agent_healthy(client, cname):
            console.print(f"[green]✓ {cname} ready.[/green]")
        else:
            console.print(f"[red]✗ {cname} failed health check (timeout).[/red]")


def _wait_for_agent_healthy(
    client: docker.DockerClient, name: str, timeout: int = 120
) -> bool:
    """Wait until container *name* reports healthy or has no HEALTHCHECK.

    Returns True if healthy (or no healthcheck), False on timeout or missing.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            cont = client.containers.get(name)
            state = cont.attrs.get("State", {})
            health = state.get("Health")
            if not health:
                return True  # no healthcheck defined → treat as healthy
            status = health.get("Status")
            if status == "healthy":
                return True
            if status == "unhealthy":
                # keep waiting; could early-exit on consecutive unhealthy
                pass
        except docker.errors.NotFound:
            return False
        time.sleep(2)
    return False


def _read_env_file(path: pathlib.Path) -> dict:
    """Read key=value lines from a .env file into a dict."""
    result = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k] = v.strip().strip('"')
    return result


def _required_images() -> List[str]:
    # Central place to keep image list – update when the platform adds new components.
    # Only core platform images; individual agent images are pulled during
    # `agentsystems up` based on the deployment config.
    return [
        "agentsystems/agent-control-plane:latest",
    ]


# Additional convenience commands (restored)
# ------------------------------------------------------------------


@app.command()
def down(
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
    _ensure_docker_installed()

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

    # Stop compose services -------------------------------------------------
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
    cmd: list[str] = [*_COMPOSE_BIN, *compose_args, "down"]
    if delete_volumes:
        cmd.append("-v")
    console.print("[cyan]⏻ Stopping core services…[/cyan]")
    _run_env(cmd, os.environ.copy())

    # Remove agent containers if requested ----------------------------------
    if delete_containers:
        client = docker.from_env()
        for c in client.containers.list(filters={"label": "agent.enabled=true"}):
            console.print(f"[cyan]⏻ Removing agent container {c.name}…[/cyan]")
            try:
                c.remove(force=True)
            except Exception as exc:  # pragma: no cover – runtime safety
                console.print(f"[red]Failed to remove {c.name}: {exc}[/red]")

    console.print(
        "[green]✓ Platform stopped."
        + (" Volumes deleted." if delete_volumes else "")
        + (" Agent containers removed." if delete_containers else "")
        + "[/green]"
    )


@app.command()
def logs(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    follow: bool = typer.Option(
        True, "--follow/--no-follow", "-f", help="Follow log output"
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
    services: List[str] = typer.Argument(
        None, help="Optional list of services to show logs for"
    ),
) -> None:
    """Stream (or dump) logs from docker compose services."""
    _ensure_docker_installed()
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
    cmd = [*_COMPOSE_BIN, *compose_args, "logs"]
    if follow:
        cmd.append("-f")
    if services:
        cmd.extend(services)
    _run_env(cmd, os.environ.copy())


# ------------------------------------------------------------------
# restart & status commands (re-added after refactor)
# ------------------------------------------------------------------


@app.command()
def restart(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--foreground",
        "-d",
        help="Run containers in background (default) or stream logs in foreground",
    ),
    wait_ready: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="After start, wait until gateway is ready (detached mode only)",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse tracing stack"
    ),
):
    """Quick bounce: `down` → `up` (non-destructive).

    Retains data volumes; wipe with `down --delete-volumes` first.
    Useful during development and CI.
    """
    _ensure_docker_installed()
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)

    # Stop current stack ----------------------------------------------------
    cmd_down: list[str] = [*_COMPOSE_BIN, *compose_args, "down"]
    console.print("[cyan]⏻ Stopping core services…[/cyan]")
    _run_env(cmd_down, os.environ.copy())

    # Start stack again ------------------------------------------------------
    cmd_up: list[str] = [*_COMPOSE_BIN, *compose_args, "up"]
    if detach:
        cmd_up.append("-d")
    console.print("[cyan]⏫ Starting core services…[/cyan]")
    _run_env(cmd_up, os.environ.copy())

    # Optional readiness wait -----------------------------------------------
    if wait_ready and detach:
        _wait_for_gateway_ready(core_compose)
    console.print("[green]✓ Restart complete.[/green]")


@app.command()
def status(
    project_dir: pathlib.Path = typer.Argument(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to an agent-platform-deployments checkout",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
):
    """List running containers and their state (`docker compose ps`)."""
    _ensure_docker_installed()
    core_compose, compose_args = _compose_args(project_dir, no_langfuse)
    cmd = [*_COMPOSE_BIN, *compose_args, "ps"]
    _run_env(cmd, os.environ.copy())


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
