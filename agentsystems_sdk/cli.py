"""Command-line interface for AgentSystems SDK.

Run `agentsystems --help` after installing to view available commands.
"""
from __future__ import annotations

import importlib.metadata as _metadata

import typer

app = typer.Typer(help="AgentSystems command-line interface")


@app.command()
def version() -> None:
    """Display the installed SDK version."""
    typer.echo(_metadata.version("agentsystems-sdk"))


if __name__ == "__main__":  # pragma: no cover – executed only when run directly
    app()
