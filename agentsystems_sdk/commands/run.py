"""Run commands in AgentSystems platform."""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import List, Optional

import requests
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def run_command(
    agent: str = typer.Argument(..., help="Name of the agent to invoke"),
    payload: str = typer.Argument(
        ...,
        help="Inline JSON string or path to a JSON file",
    ),
    input_files: List[pathlib.Path] = typer.Option(
        None,
        "--input-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="One or more files to upload alongside the JSON payload (pass multiple paths after --input-file)",
    ),
    gateway: str = typer.Option(
        None,
        "--gateway",
        envvar="GATEWAY_BASE_URL",
        help="Gateway base URL (default http://localhost:8080)",
    ),
    poll_interval: float = typer.Option(
        2.0, "--interval", "-i", help="Seconds between status polls"
    ),
    token: Optional[str] = typer.Option(
        None, "--token", "-t", help="Bearer token for Authorization header"
    ),
):
    """Invoke agent with given JSON payload and stream progress until completion."""
    gateway_base = gateway or os.getenv("GATEWAY_BASE_URL", "http://localhost:8080")
    invoke_url = f"{gateway_base.rstrip('/')}/invoke/{agent}"

    # Read JSON payload (inline string or file path)
    try:
        if os.path.isfile(payload):
            payload_data = json.loads(pathlib.Path(payload).read_text(encoding="utf-8"))
        else:
            payload_data = json.loads(payload)
    except Exception as exc:
        typer.secho(f"Invalid JSON payload: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = (
            f"Bearer {token}" if not token.startswith("Bearer ") else token
        )

    console.print(f"[cyan]⇢ Invoking {agent}…[/cyan]")

    try:
        if input_files:
            files = [("file", (path.name, open(path, "rb"))) for path in input_files]
            data = {"json": json.dumps(payload_data)}
            response = requests.post(
                invoke_url, files=files, data=data, headers=headers, timeout=60
            )
        else:
            headers.setdefault("Content-Type", "application/json")
            response = requests.post(
                invoke_url, json=payload_data, headers=headers, timeout=60
            )

        response.raise_for_status()
        invoke_result = response.json()

        thread_id = invoke_result.get("thread_id")
        if not thread_id:
            typer.secho("No thread_id in response", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        console.print(f"[green]✓ Thread ID: {thread_id}[/green]")

        # Poll for status using the status_url from response
        status_url = f"{gateway_base.rstrip('/')}{invoke_result.get('status_url')}"  # already contains leading /
        result_url = f"{gateway_base.rstrip('/')}{invoke_result.get('result_url')}"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for completion...", total=None)

            while True:
                time.sleep(poll_interval)

                try:
                    status_response = requests.get(status_url, headers=headers)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                except Exception as exc:
                    console.print(f"[red]Status poll failed: {exc}[/red]")
                    time.sleep(poll_interval)
                    continue

                state = (
                    status_data.get("state", "unknown") if status_data else "unknown"
                )

                # Update progress display
                prog_info = status_data.get("progress", {}) if status_data else {}
                desc = prog_info.get("current", state) if prog_info else state
                progress.update(task, description=desc)

                if state == "completed":
                    break
                elif state == "failed":
                    error_msg = (
                        status_data.get("error", "Unknown error")
                        if status_data
                        else "Unknown error"
                    )
                    console.print(f"[red]✗ Failed: {error_msg}[/red]")
                    raise typer.Exit(code=1)

        # Get final result
        result_response = requests.get(result_url, headers=headers)
        result_response.raise_for_status()
        result_data = result_response.json()

        console.print("[green]✓ Invocation finished. Result:[/green]")
        console.print(json.dumps(result_data, indent=2))

    except requests.RequestException as exc:
        typer.secho(f"Request error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.secho(f"Unexpected error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    finally:
        # Files are automatically closed by requests when the request completes
        pass
