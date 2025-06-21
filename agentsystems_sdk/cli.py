"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

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
def version() -> None:
    """Display the installed SDK version."""
    typer.echo(_metadata.version("agentsystems-sdk"))


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
