"""Up command for starting the AgentSystems platform."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
from enum import Enum
from typing import Dict, List, Optional

import docker
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..utils import (
    compose_args,
    ensure_docker_installed,
    ensure_agents_net,
    run_command_with_env,
    wait_for_gateway_ready,
    cleanup_langfuse_init_vars,
)

console = Console()


class AgentStartMode(str, Enum):
    """Agent startup modes."""

    none = "none"
    create = "create"
    all = "all"


def wait_for_agent_healthy(
    client: docker.DockerClient, name: str, timeout: int = 120
) -> bool:
    """Wait until container reports healthy or has no HEALTHCHECK.

    Args:
        client: Docker client
        name: Container name
        timeout: Max wait time in seconds

    Returns:
        True if healthy (or no healthcheck), False on timeout
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


def setup_agents_from_config(
    cfg: Config, project_dir: pathlib.Path, mode: AgentStartMode = AgentStartMode.create
) -> None:
    """Login to each enabled registry in an isolated config & start agents.

    We always log in using credentials specified in `.env` / env-vars, never
    relying on the user's global Docker credentials. A temporary DOCKER_CONFIG
    directory keeps this session separate so we don't clobber or depend on the
    operator's normal login state.

    Args:
        cfg: Config object with agents and registries
        project_dir: Project directory path
        mode: Agent startup mode
    """
    import tempfile
    from collections import defaultdict

    client = docker.from_env()
    ensure_agents_net()

    # Build mapping of registry key -> list[Agent]
    agents_by_reg: Dict[str, List] = defaultdict(list)
    for agent in cfg.agents:
        if agent.registry:
            agents_by_reg[agent.registry].append(agent)

    def _image_exists(ref: str, env: dict) -> bool:
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

    # Process each registry and its agents
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

    # ------------------------------------------------------------------
    # 3. Create/start containers based on *mode*
    if mode == AgentStartMode.none:
        return

    # Start containers
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
            if not wait_for_agent_healthy(client, cname):
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

        # Build docker command
        if mode == AgentStartMode.create:
            cmd = ["docker", "create"]
        else:  # mode == AgentStartMode.all
            cmd = ["docker", "run", "-d"]

        cmd.extend(
            [
                "--restart",
                "unless-stopped",
                "--name",
                cname,
                "--network",
                "agents-int",
                "--env-file",
                str(env_file_path) if env_file_path.exists() else "/dev/null",
            ]
        )

        # labels
        for k, v in labels.items():
            cmd.extend(["--label", f"{k}={v}"])
        # env overrides
        for k, v in agent.overrides.get("env", {}).items():
            cmd.extend(["--env", f"{k}={v}"])

        # ----- Artifact volume mounts & env vars --------------------------
        # Mount full artifacts volume – agent manages its own subdirectories
        # Artifact permissions are enforced at the application level via agentsystems-config.yml
        cmd.extend(["--volume", "agentsystems_agentsystems-artifacts:/artifacts"])

        # gateway proxy env
        cmd.extend(
            [
                "--env",
                "HTTP_PROXY=http://gateway:3128",
                "--env",
                "HTTPS_PROXY=http://gateway:3128",
                "--env",
                "NO_PROXY=gateway,localhost,127.0.0.1",
            ]
        )
        # port mapping (random host port)
        cmd.extend(["-p", port])
        # image
        cmd.append(agent.image)

        console.print(f"[cyan]▶ preparing {cname} ({agent.image})…[/cyan]")
        subprocess.run(cmd, check=True, env=env_base)

        if mode == AgentStartMode.all:
            # Wait for health only when container started
            if wait_for_agent_healthy(client, cname):
                console.print(f"[green]✓ {cname} ready.[/green]")
            else:
                console.print(f"[red]✗ {cname} failed health check (timeout).[/red]")


def up_command(
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
    agents_mode: AgentStartMode = typer.Option(
        AgentStartMode.create,
        "--agents",
        help="Agent startup mode: all (start), create (pull & create containers stopped), none (skip agents)",
        show_default=True,
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

    ensure_docker_installed()

    # Use isolated Docker config for the entire session
    isolated_cfg = tempfile.TemporaryDirectory(prefix="agentsystems-docker-config-")
    env_base = os.environ.copy()
    env_base["DOCKER_CONFIG"] = isolated_cfg.name

    # .env gets loaded later – keep env_base in sync
    def _sync_env_base() -> None:
        env_base.update(os.environ)

    # Optional upfront login to docker.io
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

    # Load agentsystems-config.yml if present
    cfg_path = project_dir / "agentsystems-config.yml"
    cfg: Config | None = None
    if cfg_path.exists():
        try:
            cfg = Config(cfg_path)
            console.print(
                f"[cyan]✓ Loaded config ({len(cfg.agents)} agents, {len(cfg.registries)} registries).[/cyan]"
            )
        except Exception as e:
            typer.secho(f"Error parsing {cfg_path}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Build compose arguments
    core_compose, compose_files = compose_args(project_dir, langfuse=not no_langfuse)

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
            run_command_with_env(compose_files + ["down", "-v"], env_base)
            prog.update(down_task, completed=1)

        up_cmd = compose_files + ["up"]
        if env_file:
            up_cmd.extend(["--env-file", str(env_file)])
        if detach:
            up_cmd.append("-d")

        prog.add_task("Starting services", total=None)
        run_command_with_env(up_cmd, env_base)

        # After successful startup, clean up init vars
        target_env_path = env_file if env_file else env_path
        if target_env_path.exists():
            cleanup_langfuse_init_vars(target_env_path)
            # Ensure variables are available for CLI itself
            load_dotenv(dotenv_path=target_env_path, override=False)
            _sync_env_base()

    # If config specified agents, ensure registries are logged in & images pulled
    if cfg:
        console.print(
            f"\n[bold cyan]Setting up {len(cfg.agents)} agent(s)...[/bold cyan]"
        )
        setup_agents_from_config(cfg, project_dir, agents_mode)

    # Restart gateway so it picks up any newly started agents
    console.print("[cyan]↻ restarting gateway to reload agent routes…[/cyan]")
    try:
        run_command_with_env(compose_files + ["restart", "gateway"], env_base)
    except Exception:
        pass

    if detach and wait_ready:
        wait_for_gateway_ready()

    console.print(
        Panel.fit(
            "✅ [bold green]Platform is running![/bold green]", border_style="green"
        )
    )

    # Cleanup temporary Docker config directory
    isolated_cfg.cleanup()
