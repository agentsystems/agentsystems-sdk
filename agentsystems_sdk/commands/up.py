"""Up command for starting the AgentSystems platform."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
from enum import Enum
from typing import Dict, List, Optional

import requests

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
from .down import down_command

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

    # Validate unique agent names before starting any operations
    agent_names = [agent.name for agent in cfg.agents]
    duplicate_names = [name for name in agent_names if agent_names.count(name) > 1]
    if duplicate_names:
        unique_duplicates = list(set(duplicate_names))
        console.print(
            f"[red]✗ Duplicate agent names detected: {', '.join(unique_duplicates)}[/red]"
        )
        console.print("[red]  Each agent must have a unique name.[/red]")
        console.print(
            "[red]  Fix: Update agent names in agentsystems-config.yml or via the UI at http://localhost:3001/configuration/agents[/red]"
        )
        raise typer.Exit(code=1)

    client = docker.from_env()
    ensure_agents_net()

    # Build mapping of registry key -> list[Agent]
    agents_by_reg: Dict[str, List] = defaultdict(list)
    for agent in cfg.agents:
        if agent.registry:
            agents_by_reg[agent.registry].append(agent)

    # Track images that failed to pull so we can skip starting their containers
    failed_pulls = []

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

        # Check if all images for this registry are already present
        env_base = os.environ.copy()
        missing_images = [
            a.image for a in agents_list if not _image_exists(a.image, env_base)
        ]

        if not missing_images:
            console.print(
                f"[green]✓ All images from {reg.url} already present, skipping login.[/green]"
            )
            continue

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
                try:
                    subprocess.run(["docker", "pull", img], check=True, env=env)
                except subprocess.CalledProcessError:
                    console.print(f"[red]✗ Failed to pull {img}[/red]")
                    console.print(
                        "[yellow]  This agent will be skipped. Common causes:[/yellow]"
                    )
                    console.print(
                        "[yellow]  - Missing or incorrect registry credentials[/yellow]"
                    )
                    console.print(
                        "[yellow]  - Image does not exist or is private[/yellow]"
                    )
                    console.print(
                        "[yellow]  Fix: Update registry credentials in the UI at http://localhost:3001/configuration/registries[/yellow]"
                    )
                    failed_pulls.append(img)

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
        # Use agent name as container name and service label for consistent routing
        cname = agent.name
        service_name = agent.name

        # Skip agents whose images failed to pull
        if agent.image in failed_pulls:
            console.print(f"[yellow]⊗ Skipping {cname} - image pull failed[/yellow]")
            continue

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

        # Mount agentsystems-config.yml for model routing via agentsystems-toolkit
        config_file_path = project_dir / "agentsystems-config.yml"
        if config_file_path.exists():
            cmd.extend(
                [
                    "--volume",
                    f"{config_file_path}:/etc/agentsystems/agentsystems-config.yml:ro",
                ]
            )

        # gateway proxy env
        cmd.extend(
            [
                "--env",
                "HTTP_PROXY=http://gateway:3128",
                "--env",
                "HTTPS_PROXY=http://gateway:3128",
                "--env",
                "NO_PROXY=gateway,localhost,127.0.0.1,ollama",
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

    # Show summary if any agents failed to start
    if failed_pulls:
        console.print(
            "\n[yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/yellow]"
        )
        console.print(
            f"[yellow]⚠  {len(failed_pulls)} agent(s) skipped due to pull failures:[/yellow]"
        )
        for img in failed_pulls:
            console.print(f"[yellow]   • {img}[/yellow]")
        console.print(
            "[yellow]   Fix registry credentials at: http://localhost:3001/configuration/registries[/yellow]"
        )
        console.print(
            "[yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/yellow]\n"
        )


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
    agent_control_plane_version: Optional[str] = typer.Option(
        None,
        "--agent-control-plane",
        "--acp",
        help="Pin agent-control-plane to specific version (e.g., 0.3.17)",
    ),
    agentsystems_ui_version: Optional[str] = typer.Option(
        None,
        "--agentsystems-ui",
        "--ui",
        help="Pin agentsystems-ui to specific version (e.g., 0.1.5)",
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

    # Always do a clean down → up to avoid stale containers/networks
    console.print(
        "[cyan]🧹 Stopping existing containers and cleaning networks...[/cyan]"
    )
    down_command(
        project_dir=project_dir,
        delete_volumes=fresh,  # Only delete volumes if --fresh flag passed
        delete_containers=False,
        delete_all=False,
        volumes=None,
        no_langfuse=no_langfuse,
    )

    # Recreate agents-net (required external network for compose)
    console.print("[cyan]🔌 Creating platform networks...[/cyan]")
    try:
        subprocess.run(
            ["docker", "network", "create", "agents-net"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Network might already exist

    # Use isolated Docker config for the entire session
    isolated_cfg = tempfile.TemporaryDirectory(prefix="agentsystems-docker-config-")
    env_base = os.environ.copy()
    env_base["DOCKER_CONFIG"] = isolated_cfg.name

    # Validate and set version tags from CLI flags if provided
    def _validate_version(version_str: str, min_version: str, component: str) -> bool:
        """Validate that version meets minimum requirements for version management features."""
        import re

        # Skip validation for special tags
        if version_str in ["latest", "main", "development"]:
            return True

        # Validate semantic version format
        if not re.match(r"^\d+\.\d+\.\d+$", version_str):
            console.print(
                f"[red]❌ Error: {component} version must be semantic version (x.y.z format)[/red]"
            )
            console.print(f"[red]   You provided: {version_str}[/red]")
            console.print("[red]   Valid examples: 0.4.0, 1.2.3[/red]")
            return False

        # Simple version comparison (works for our use case)
        def version_tuple(v):
            return tuple(map(int, v.split(".")))

        try:
            if version_tuple(version_str) < version_tuple(min_version):
                console.print(
                    f"[red]❌ Error: {component} version {version_str} does not support version management[/red]"
                )
                console.print(
                    f"[red]   Minimum required {component}: {min_version}[/red]"
                )
                console.print(
                    "[red]   This version introduced /version and /component-versions endpoints[/red]"
                )
                return False
        except Exception:
            console.print(f"[red]❌ Error: Invalid version format: {version_str}[/red]")
            return False

        return True

    if agent_control_plane_version:
        if not _validate_version(
            agent_control_plane_version, "0.4.0", "agent-control-plane"
        ):
            raise typer.Exit(1)
        env_base["ACP_TAG"] = agent_control_plane_version
        console.print(
            f"[yellow]📌 Pinning agent-control-plane to version: {agent_control_plane_version}[/yellow]"
        )

    if agentsystems_ui_version:
        if not _validate_version(agentsystems_ui_version, "0.2.0", "agentsystems-ui"):
            raise typer.Exit(1)
        env_base["UI_TAG"] = agentsystems_ui_version
        console.print(
            f"[yellow]📌 Pinning agentsystems-ui to version: {agentsystems_ui_version}[/yellow]"
        )

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
        # Note: down already called above, no need to call it again
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

    # Check for missing Ollama models and provide instructions
    has_missing_models = _check_missing_ollama_models(cfg, console)

    # Display prominent UI link with conditional message
    console.print()
    if has_missing_models:
        ui_message = "🌐 [bold cyan]AgentSystems UI Ready![/bold cyan]\n\nPull models via command above, then visit:\n\n👉 [bold blue]http://localhost:3001[/bold blue]"
    else:
        ui_message = "🌐 [bold cyan]AgentSystems UI Ready![/bold cyan]\n\n👉 [bold blue]http://localhost:3001[/bold blue]"

    console.print(
        Panel.fit(
            ui_message,
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Cleanup temporary Docker config directory
    isolated_cfg.cleanup()


def _check_missing_ollama_models(cfg: Config, console: Console) -> bool:
    """Check for missing local Ollama models and provide download instructions.

    Returns:
        True if any local Ollama models are missing, False otherwise.
    """
    # Read model_connections directly from YAML file since Config class doesn't include it
    try:
        import yaml

        with open(cfg.path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
        model_connections = raw_config.get("model_connections", {})
    except Exception:
        return False  # Skip if can't read config

    if not model_connections:
        return False

    # Parse .env file to resolve environment variables
    project_dir = pathlib.Path.cwd()
    env_file = project_dir / ".env"
    env_vars = {}

    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            pass  # Continue without env vars if parsing fails

    # Find LOCAL Ollama models in configuration
    local_ollama_models = []
    for model_id, model_config in model_connections.items():
        if model_config.get("hosting_provider") == "ollama" and model_config.get(
            "enabled", True
        ):
            # Check if this is a local Ollama instance
            base_url_env_name = model_config.get("auth", {}).get("base_url")
            if base_url_env_name:
                # Resolve environment variable from .env file or actual env
                base_url = env_vars.get(base_url_env_name) or os.getenv(
                    base_url_env_name, ""
                )
                # Only check local Ollama instances (not remote ones)
                if base_url == "http://ollama:11434":
                    local_ollama_models.append(
                        model_config.get("hosting_provider_model_id", model_id)
                    )

    if not local_ollama_models:
        return False

    try:
        # Check if local Ollama service is available
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            return False

        available_models = {
            model["name"] for model in response.json().get("models", [])
        }
        missing_models = [
            model for model in local_ollama_models if model not in available_models
        ]

        if missing_models:
            console.print()
            console.print("📋 Run these commands to download missing models:")
            console.print()
            for model in missing_models:
                console.print(
                    f"[bold green]docker exec agentsystems-ollama-1 ollama pull {model}[/bold green]"
                )
            console.print()
            console.print(
                "📄 By downloading, you accept the model's terms regarding licensing, usage, etc."
            )
            console.print()
            return True  # Found missing models

        return False  # All models present

    except Exception:
        # Silently skip if Ollama check fails - don't break the user experience
        return False
