"""Start the AgentSystems platform."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
from enum import Enum
from typing import Optional

import docker
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..utils import (
    ensure_docker_installed,
    compose_args,
    wait_for_gateway_ready,
    run_command_with_env,
)
from .init import cleanup_init_vars

console = Console()


class AgentStartMode(str, Enum):
    """Agent startup mode options."""

    none = "none"
    create = "create"
    all = "all"


def wait_for_agent_healthy(
    client: docker.DockerClient, name: str, timeout: int = 120
) -> bool:
    """Wait until container reports healthy or has no HEALTHCHECK.

    Args:
        client: Docker client instance
        name: Container name
        timeout: Maximum time to wait in seconds

    Returns:
        True if healthy (or no healthcheck), False on timeout or missing.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            container = client.containers.get(name)

            # No health check defined
            if "Health" not in container.attrs["State"]:
                return True

            health = container.attrs["State"]["Health"]["Status"]
            if health == "healthy":
                return True
            elif health == "unhealthy":
                return False

            time.sleep(2)
        except docker.errors.NotFound:
            return False

    return False


def setup_agents_from_config(
    cfg: Config, project_dir: pathlib.Path, mode: AgentStartMode = AgentStartMode.create
) -> None:
    """Login to each enabled registry in an isolated config & start agents.

    Args:
        cfg: AgentSystems configuration
        project_dir: Project directory path
        mode: Agent startup mode
    """
    if mode == AgentStartMode.none:
        console.print("[yellow]⇒ Skipping agent setup (--agents=none)[/yellow]")
        return

    isolated_docker_config = tempfile.TemporaryDirectory(prefix="agentsystems-agents-")
    env_isolated = os.environ.copy()
    env_isolated["DOCKER_CONFIG"] = isolated_docker_config.name

    console.print(f"\n[bold cyan]Setting up {len(cfg.agents)} agent(s)...[/bold cyan]")

    # Process each registry
    for reg_id, reg in cfg.enabled_registries().items():
        env_name = f"{reg_id.upper()}_PAT"
        pat = os.getenv(env_name)

        if not pat:
            console.print(
                f"[yellow]⚠ No {env_name} found, skipping {reg_id} login[/yellow]"
            )
            continue

        console.print(f"[cyan]⇒ Logging into {reg.url} as {reg.username}[/cyan]")

        # Get password command based on registry type
        if reg.type == "ghcr":
            pw_cmd = ["echo", pat]
        else:
            # ECR or other registries
            pw_cmd = reg.password_command.replace("{pat}", pat).split()

        try:
            proc_pw = subprocess.run(
                pw_cmd, capture_output=True, text=True, check=True, env=env_isolated
            )
            password = proc_pw.stdout.strip()
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Password command failed: {e.stderr}[/red]")
            continue

        # Docker login
        try:
            subprocess.run(
                ["docker", "login", reg.url, "-u", reg.username, "--password-stdin"],
                input=f"{password}\n".encode(),
                check=True,
                env=env_isolated,
            )
            console.print(f"[green]✓ Logged into {reg_id}[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[red]✗ Login to {reg_id} failed[/red]")

    # Process agents
    client = docker.from_env()

    for agent in cfg.agents:
        if agent.disabled:
            console.print(f"[yellow]⇒ Skipping disabled agent: {agent.name}[/yellow]")
            continue

        # Pull image
        console.print(f"[cyan]⇒ Pulling {agent.image}...[/cyan]")
        try:
            subprocess.run(
                ["docker", "pull", agent.image],
                check=True,
                env=env_isolated,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            console.print(f"[red]✗ Failed to pull {agent.image}[/red]")
            continue

        # Check if container exists
        cname = f"agentsystems-{agent.name}-1"

        try:
            client.containers.get(cname)
            console.print(f"[green]✓ {cname} already running.[/green]")
            if not wait_for_agent_healthy(client, cname):
                console.print(f"[red]✗ {cname} failed health check (timeout).[/red]")
            continue
        except docker.errors.NotFound:
            pass

        # Create container
        console.print(f"[cyan]⇒ Creating container for {agent.name}[/cyan]")

        env_vars = agent.environment.copy() if agent.environment else {}
        env_vars.update(
            {
                "LANGFUSE_HOST": os.getenv("LANGFUSE_HOST", "http://langfuse-web:3000"),
                "LANGFUSE_PUBLIC_KEY": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                "LANGFUSE_SECRET_KEY": os.getenv("LANGFUSE_SECRET_KEY", ""),
            }
        )

        # Apply env_from patterns
        if agent.env_from:
            for pattern in agent.env_from:
                prefix = pattern.rstrip("*")
                for k, v in os.environ.items():
                    if k.startswith(prefix):
                        env_vars[k] = v

        labels = {
            "agent.enabled": "true",
            "agent.port": str(agent.port),
            "agent.name": agent.name,
        }

        try:
            container = client.containers.create(
                agent.image,
                name=cname,
                hostname=agent.name,
                environment=env_vars,
                labels=labels,
                network="agents_net",
                restart_policy={"Name": "unless-stopped"},
                volumes={
                    "/var/run/docker.sock": {
                        "bind": "/var/run/docker.sock",
                        "mode": "ro",
                    },
                    "agentsystems_artifacts": {"bind": "/artifacts", "mode": "rw"},
                },
            )

            if mode == AgentStartMode.all:
                container.start()
                console.print(f"[green]✓ Started {agent.name}[/green]")

                if wait_for_agent_healthy(client, cname):
                    console.print(f"[green]✓ {cname} ready.[/green]")
                else:
                    console.print(
                        f"[red]✗ {cname} failed health check (timeout).[/red]"
                    )
            else:
                console.print(f"[green]✓ Created {agent.name} (stopped)[/green]")

        except docker.errors.APIError as e:
            console.print(f"[red]✗ Failed to create {agent.name}: {e}[/red]")

    isolated_docker_config.cleanup()


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

    # Sync environment after loading .env
    def sync_env_base() -> None:
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
                f"[cyan]✓ Loaded config ({len(cfg.agents)} agents, {len(cfg.enabled_registries())} registries).[/cyan]"
            )
        except Exception as e:
            typer.secho(f"Error parsing {cfg_path}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    project_dir = project_dir.expanduser()
    if not project_dir.exists():
        typer.secho(f"Directory {project_dir} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Build compose arguments
    compose_args_list = compose_args(project_dir, langfuse=not no_langfuse)

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
            run_command_with_env([*compose_args_list, "down", "-v"], env_base)
            prog.update(down_task, completed=1)

        up_cmd = [*compose_args_list, "up"]
        if env_file:
            up_cmd.extend(["--env-file", str(env_file)])
        if detach:
            up_cmd.append("-d")

        prog.add_task("Starting services", total=None)
        run_command_with_env(up_cmd, env_base)

        # Clean up init vars after successful startup
        target_env_path = env_file if env_file else env_path
        if target_env_path.exists():
            cleanup_init_vars(target_env_path)
            # Ensure variables are available for CLI
            load_dotenv(dotenv_path=target_env_path, override=False)
            sync_env_base()

    # Setup agents from config if specified
    if cfg:
        setup_agents_from_config(cfg, project_dir, agents_mode)

    # Restart gateway to reload agent routes
    console.print("[cyan]↻ restarting gateway to reload agent routes…[/cyan]")
    try:
        run_command_with_env([*compose_args_list, "restart", "gateway"], env_base)
    except Exception:
        pass

    if detach and wait_ready:
        # Extract gateway URL from compose file
        gateway_url = "http://localhost:18080"
        wait_for_gateway_ready(gateway_url)

    console.print(
        Panel.fit(
            "✅ [bold green]Platform is running![/bold green]", border_style="green"
        )
    )

    # Cleanup temporary Docker config
    isolated_cfg.cleanup()
