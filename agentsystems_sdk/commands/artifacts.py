"""Manage artifacts directory for AgentSystems."""

from __future__ import annotations

import pathlib
from typing import Optional

import typer


def artifacts_path_command(
    thread_id: str = typer.Argument(
        ...,
        help="Thread ID for the artifact directory",
    ),
    relative_path: Optional[str] = typer.Argument(
        None,
        help="Optional path inside in/out folder to append",
    ),
    input_dir: bool = typer.Option(
        False,
        "--input/--output",
        help="Return path under in/ instead of out/ (default out)",
    ),
) -> None:
    """Print a fully-qualified path inside the shared artifacts volume.

    Thread-centric structure: /artifacts/{thread_id}/{in,out}/

    Examples::

        # Path to thread's output folder
        agentsystems artifacts-path abc123

        # Path to specific file in thread's input folder
        agentsystems artifacts-path abc123 data.txt --input
    """
    base = pathlib.Path("/artifacts") / thread_id / ("in" if input_dir else "out")
    if relative_path:
        base = base / relative_path
    typer.echo(str(base))
