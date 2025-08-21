"""Shared utilities for AgentSystems CLI commands."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import time
from typing import List, Dict, Tuple, Optional

import docker
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Detect Docker Compose CLI once at import time
if shutil.which("docker-compose"):
    COMPOSE_BIN: List[str] = ["docker-compose"]
else:
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        COMPOSE_BIN = ["docker", "compose"]
    except Exception:
        COMPOSE_BIN = []


def run_command(cmd: List[str]) -> subprocess.CompletedProcess[bytes]:
    """Run command inheriting the current environment.

    Args:
        cmd: Command and arguments to execute

    Raises:
        typer.Exit: If the command fails, exits with the same exit code
    """
    try:
        result = subprocess.run(cmd, check=True)
        return result
    except subprocess.CalledProcessError as exc:
        typer.secho(f"Command failed: {' '.join(cmd)}", fg=typer.colors.RED)
        raise typer.Exit(exc.returncode) from exc


def run_command_with_env(cmd: List[str], env: Dict[str, str]) -> int:
    """Run command with a custom environment mapping.

    Args:
        cmd: Command and arguments to execute
        env: Environment variables to use

    Raises:
        typer.Exit: If the command fails, exits with the same exit code
    """
    try:
        result = subprocess.check_call(cmd, env=env)
        return result
    except subprocess.CalledProcessError as exc:
        error_msg = f"Command failed: {' '.join(cmd)}"
        typer.secho(error_msg, fg=typer.colors.RED)
        raise typer.Exit(exc.returncode) from exc


def ensure_docker_installed() -> None:
    """Check if Docker CLI is installed and exit if not found."""
    if shutil.which("docker") is None:
        typer.secho(
            "Docker CLI not found. Please install Docker Desktop and retry.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def docker_login_if_needed(token: Optional[str]) -> None:
    """Login to Docker Hub if a token is provided.

    Args:
        token: Docker Hub Org Access Token (optional)
    """
    if not token:
        return
    try:
        # Use Popen to avoid potential deadlocks with stdin/stdout when progress is active
        import os

        proc = subprocess.Popen(
            ["docker", "login", "--username", "agentsystems", "--password-stdin"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )

        stdout, stderr = proc.communicate(input=token, timeout=30)
        if proc.returncode != 0:
            typer.secho(
                f"Docker login failed: {stderr}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        typer.secho("✓ Docker login successful", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(
            f"Docker login error: {str(e)}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def ensure_agents_net() -> None:
    """Create the 'agents_net' Docker network if it doesn't exist."""
    net_name = "agents_net"
    client = docker.from_env()

    try:
        client.networks.get(net_name)
        return  # Network already exists
    except docker.errors.NotFound:
        pass

    # Create the network
    try:
        client.networks.create(
            net_name,
            driver="bridge",
            options={"com.docker.network.bridge.host_binding_ipv4": "127.0.0.1"},
        )
        typer.secho(f"✓ Created network '{net_name}'", fg=typer.colors.GREEN)
    except docker.errors.APIError as e:
        typer.secho(
            f"Failed to create network '{net_name}': {e}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)


def compose_args(
    base_path: pathlib.Path,
    *,
    langfuse: bool = True,
) -> Tuple[pathlib.Path, List[str]]:
    """Build docker-compose command arguments.

    Args:
        base_path: Base path for the project
        langfuse: Whether to include Langfuse configuration

    Returns:
        Tuple of (core compose file path, list of full compose command args)
    """
    if not COMPOSE_BIN:
        typer.secho(
            "Docker Compose not found. Install via Docker Desktop or standalone.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    args = COMPOSE_BIN[:]

    compose_file = base_path / "compose" / "local" / "docker-compose.yml"

    # Check if compose file exists
    if not compose_file.exists():
        typer.secho(
            f"Docker Compose file not found: {compose_file}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    args.extend(["-f", str(compose_file)])

    if langfuse:
        langfuse_file = base_path / "langfuse" / "docker-compose.langfuse.yml"
        if langfuse_file.exists():
            args.extend(["-f", str(langfuse_file)])

    args.extend(["-p", "agentsystems"])
    return compose_file, args


def wait_for_gateway_ready(
    gateway_url: str = "http://localhost:18080",
    timeout: int = 30,
    interval: float = 0.5,
) -> bool:
    """Wait for the AgentSystems gateway to be ready.

    Args:
        gateway_url: Gateway URL to check
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds

    Returns:
        True if gateway is ready, False if timeout
    """
    import requests

    health_url = f"{gateway_url}/health"
    deadline = time.time() + timeout

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Waiting for gateway to be ready...", total=None)

        while time.time() < deadline:
            try:
                resp = requests.get(health_url, timeout=5)
                if resp.status_code == 200:
                    progress.update(task, description="✓ Gateway is ready!")
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(interval)

        progress.update(task, description="✗ Gateway startup timeout")
        return False


def read_env_file(path: pathlib.Path) -> Dict[str, str]:
    """Read environment variables from a .env file.

    Args:
        path: Path to the .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_required_images() -> List[str]:
    """Get list of required Docker images.

    Central place to keep image list – update when the platform adds new components.
    Only core platform images; individual agent images are pulled during
    `agentsystems up` based on the deployment config.

    Returns:
        List of Docker image names
    """
    # Control plane and other images are pulled during 'agentsystems up'
    # when the docker-compose file is processed, not during init
    return []


def cleanup_langfuse_init_vars(env_path: pathlib.Path) -> None:
    """Comment-out one-time LANGFUSE_INIT_* vars after first successful start.

    These initialization variables are only needed on first startup to create
    the initial Langfuse organization and user. After that, they should be
    commented out to prevent confusion.

    Args:
        env_path: Path to the .env file to clean up
    """
    content = env_path.read_text()

    # Check if already cleaned up
    if (
        "# --- Langfuse initialization values (no longer used after first start) ---"
        in content
    ):
        return

    lines = content.splitlines()
    init_lines: List[str] = []
    other_lines: List[str] = []

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
