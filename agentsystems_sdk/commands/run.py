"""Run commands inside AgentSystems containers."""

from __future__ import annotations

import pathlib
from typing import List

import typer
from rich.console import Console

from ..utils import (
    ensure_docker_installed,
    compose_args,
)

console = Console()


def run_command_cli(
    service: str = typer.Argument(..., help="Service name (e.g., gateway, postgres)"),
    cmd: List[str] = typer.Argument(
        ..., help="Command and arguments to run inside the container"
    ),
    project_dir: pathlib.Path = typer.Option(
        ".",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to agent-platform-deployments",
    ),
    no_langfuse: bool = typer.Option(
        False, "--no-langfuse", help="Disable Langfuse stack"
    ),
) -> None:
    """Execute a command inside a running service container.

    This is equivalent to `docker compose exec <service> <cmd>`.

    Examples:
      agentsystems run gateway env                    # list env vars in gateway
      agentsystems run postgres psql -U agent_cp      # psql shell
      agentsystems run langfuse-web npx prisma studio # Prisma studio
    """
    ensure_docker_installed()

    compose_args_list = compose_args(project_dir, langfuse=not no_langfuse)

    exec_cmd = [*compose_args_list, "exec", service] + list(cmd)

    # Use the utility function (avoiding name collision)
    from ..utils import run_command as run_cmd

    run_cmd(exec_cmd)
