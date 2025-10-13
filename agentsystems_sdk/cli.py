"""Command-line interface for the AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""

from __future__ import annotations

import importlib.metadata as _metadata
import os
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from agentsystems_sdk.commands import (
    init_command,
    up_command,
    down_command,
    logs_command,
    restart_command,
    status_command,
    run_command,
    artifacts_path_command,
    clean_command,
    update_command,
    version_command,
    versions_command,
    index_commands,
)

# Load .env before Typer parses env-var options
dotenv_global = os.getenv("AGENTSYSTEMS_GLOBAL_ENV")
if dotenv_global:
    dotenv_global = os.path.expanduser(dotenv_global)
    if os.path.exists(dotenv_global):
        load_dotenv(dotenv_path=dotenv_global)
# Fallback to .env in current working directory (if any)
load_dotenv()

console = Console()

# Create the main Typer app
app = typer.Typer(
    name="agentsystems",
    help="AgentSystems SDK - Deploy and manage AI agent platforms",
    no_args_is_help=True,
    rich_markup_mode="markdown",
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        try:
            version = _metadata.version("agentsystems-sdk")
        except _metadata.PackageNotFoundError:
            version = "unknown (development mode)"
        console.print(f"agentsystems version: {version}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """AgentSystems SDK - Deploy and manage AI agent platforms.

    Use `agentsystems COMMAND --help` for detailed help on each command.
    """
    pass


# Register all commands
app.command(name="init")(init_command)
app.command(name="up")(up_command)
app.command(name="down")(down_command)
app.command(name="logs")(logs_command)
app.command(name="restart")(restart_command)
app.command(name="status")(status_command)
app.command(name="run")(run_command)
app.command(name="artifacts-path")(artifacts_path_command)
app.command(name="clean")(clean_command)
app.command(name="update")(update_command)
app.command(name="version")(version_command)
app.command(name="versions")(versions_command)

# Register index sub-commands
app.add_typer(index_commands)


if __name__ == "__main__":
    app()
