"""Initialize a new AgentSystems project."""

from __future__ import annotations

import pathlib
import re
import shutil
import sys
import uuid
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from dotenv import set_key

from ..utils import (
    ensure_docker_installed,
    docker_login_if_needed,
    run_command,
    get_required_images,
)

console = Console()


def cleanup_init_vars(env_path: pathlib.Path) -> None:
    """Comment out LANGFUSE_INIT_* variables from .env file after first startup.

    Args:
        env_path: Path to the .env file
    """
    init_vars = [
        "LANGFUSE_INIT_ORG_ID",
        "LANGFUSE_INIT_ORG_NAME",
        "LANGFUSE_INIT_PROJECT_ID",
        "LANGFUSE_INIT_PROJECT_NAME",
        "LANGFUSE_INIT_PROJECT_PUBLIC_KEY",
        "LANGFUSE_INIT_PROJECT_SECRET_KEY",
        "LANGFUSE_INIT_USER_EMAIL",
        "LANGFUSE_INIT_USER_NAME",
        "LANGFUSE_INIT_USER_PASSWORD",
        "LANGFUSE_INIT_ADMIN_EMAIL",  # Also check older names
        "LANGFUSE_INIT_ADMIN_PASSWORD",
    ]

    try:
        lines = env_path.read_text().splitlines()
        cleaned_lines = []
        header_added = False

        for line in lines:
            if any(line.startswith(f"{var}=") for var in init_vars):
                if not header_added:
                    cleaned_lines.append("")
                    cleaned_lines.append(
                        "# Langfuse initialization values (used only on first startup)"
                    )
                    header_added = True
                cleaned_lines.append(f"# {line}")
            else:
                cleaned_lines.append(line)

        env_path.write_text("\n".join(cleaned_lines) + "\n")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not clean init vars: {e}[/yellow]")


def init_command(
    project_dir: Optional[pathlib.Path] = typer.Argument(
        None,
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
    ),
    branch: str = typer.Option("main", help="Branch to clone"),
    gh_token: str | None = typer.Option(
        None,
        "--gh-token",
        envvar="GITHUB_TOKEN",
        help="GitHub Personal Access Token for private template repo",
    ),
    docker_token: str | None = typer.Option(
        None,
        "--docker-token",
        envvar="DOCKER_OAT",
        help="Docker Hub Org Access Token for private images",
    ),
):
    """Clone the agent deployment template and pull required Docker images.

    Steps:
    1. Clone the `agent-platform-deployments` template repo into *project_dir*.
    2. Pull Docker images required by the platform.
    """
    # Determine target directory
    if project_dir is None:
        if not sys.stdin.isatty():
            typer.secho(
                "TARGET_DIR argument required when running non-interactively.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        default_name = "agent-platform-deployments"
        dir_input = typer.prompt("Directory to create", default=default_name)
        project_dir = pathlib.Path(dir_input)
        if not project_dir.is_absolute():
            project_dir = pathlib.Path.cwd() / project_dir

    project_dir = project_dir.expanduser()
    if project_dir.exists() and any(project_dir.iterdir()):
        typer.secho(
            f"Directory {project_dir} is not empty – aborting.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    # Prompt for missing tokens only if running interactively

    # ---------- Langfuse initial setup prompts ----------
    if sys.stdin.isatty():
        console.print("\n[bold cyan]Langfuse initial setup[/bold cyan]")

        org_name = typer.prompt("Organization name", default="ExampleOrg")
        org_id = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"
        project_id = "default"
        project_name = "Default"
        user_name = "Admin"

        while True:
            email = typer.prompt("Admin email")
            if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                break
            console.print("[red]Please enter a valid email address.[/red]")

        while True:
            password = typer.prompt("Admin password (min 8 chars)", hide_input=True)
            if len(password) >= 8:
                break
            console.print("[red]Password must be at least 8 characters.[/red]")

        pub_key = f"pk-lf-{uuid.uuid4()}"
        secret_key = f"sk-lf-{uuid.uuid4()}"
    else:
        org_name = "ExampleOrg"
        org_id = "org"
        project_id = "default"
        project_name = "Default"
        user_name = "Admin"
        email = ""
        password = ""
        pub_key = f"pk-lf-{uuid.uuid4()}"
        secret_key = f"sk-lf-{uuid.uuid4()}"

    if gh_token is None and sys.stdin.isatty():
        gh_token = (
            typer.prompt(
                "GitHub token (leave blank if repo is public)",
                default="",
                hide_input=True,
            )
            or None
        )

    if docker_token is None and sys.stdin.isatty():
        docker_token = (
            typer.prompt(
                "Docker org access token (leave blank if images are public)",
                default="",
                hide_input=True,
            )
            or None
        )

    base_repo_url = "https://github.com/agentsystems/agent-platform-deployments.git"
    clone_repo_url = (
        base_repo_url.replace("https://", f"https://{gh_token}@")
        if gh_token
        else base_repo_url
    )

    # ---------- UI banner ----------
    console.print(
        Panel.fit(
            "🚀 [bold cyan]AgentSystems SDK[/bold cyan] – initialization",
            border_style="bright_cyan",
        )
    )

    # ---------- Progress ----------
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(style="bright_magenta"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Clone repository
        clone_task = progress.add_task("Cloning template repo", total=None)
        _display_url = re.sub(r"https://[^@]+@", "https://", clone_repo_url)

        run_command(
            ["git", "clone", "--branch", branch, clone_repo_url, str(project_dir)]
        )
        progress.update(clone_task, completed=1)

        # Remove remote origin to avoid accidental pushes to template repo
        run_command(["git", "-C", str(project_dir), "remote", "remove", "origin"])

        # ---------- Write Langfuse .env ----------
        env_example = project_dir / ".env.example"
        env_file = project_dir / ".env"
        if env_example.exists() and not env_file.exists():
            shutil.copy(env_example, env_file)
            env_file = project_dir / ".env"
        else:
            env_file = env_file if env_file.exists() else env_example

        cfg_pairs = {
            "LANGFUSE_INIT_ORG_ID": org_id,
            "LANGFUSE_INIT_ORG_NAME": org_name,
            "LANGFUSE_INIT_PROJECT_ID": project_id,
            "LANGFUSE_INIT_PROJECT_NAME": project_name,
            "LANGFUSE_INIT_USER_NAME": user_name,
            "LANGFUSE_INIT_USER_EMAIL": email,
            "LANGFUSE_INIT_USER_PASSWORD": password,
            "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": pub_key,
            "LANGFUSE_INIT_PROJECT_SECRET_KEY": secret_key,
            # Runtime vars (must be *unquoted* for Docker)
            "LANGFUSE_HOST": "http://langfuse-web:3000",
            "LANGFUSE_PUBLIC_KEY": pub_key,
            "LANGFUSE_SECRET_KEY": secret_key,
        }

        for k, v in cfg_pairs.items():
            # Quote only the one-shot INIT vars; runtime vars stay raw
            value_to_write = f'"{v}"' if k.startswith("LANGFUSE_INIT_") else str(v)
            set_key(str(env_file), k, value_to_write, quote_mode="never")

        # Check Docker
        docker_task = progress.add_task("Checking Docker", total=1)
        ensure_docker_installed()
        progress.update(docker_task, completed=1)

        # Docker login if token provided
        if docker_token:
            login_task = progress.add_task("Logging into Docker Hub", total=1)
            progress.stop()  # Stop progress display temporarily
            try:
                docker_login_if_needed(docker_token)
            finally:
                progress.start()  # Always restart progress
            progress.update(login_task, completed=1)

        # Pull required images
        required_images = get_required_images()

        if not required_images:
            console.print("[yellow]Warning: No images to pull[/yellow]")
        else:
            pull_task = progress.add_task(
                "Pulling Docker images", total=len(required_images)
            )

            for img in required_images:
                progress.update(pull_task, description=f"Pulling {img}")
                progress.stop()  # Stop progress to show docker output
                try:
                    run_command(["docker", "pull", img])
                except typer.Exit:
                    if docker_token is None and sys.stdin.isatty():
                        docker_token = typer.prompt(
                            "Pull failed – provide Docker org token", hide_input=True
                        )
                        docker_login_if_needed(docker_token)
                        run_command(["docker", "pull", img])
                    else:
                        raise
                finally:
                    progress.start()  # Always restart progress
                progress.advance(pull_task)

    # ---------- Completion message ----------
    display_dir = project_dir.name
    next_steps = (
        f"✅ Initialization complete!\n\n"
        f"Next steps:\n"
        f"  1. cd {display_dir}\n"
        f"  2. Review .env and adjust if needed.\n"
        f"  3. Run: agentsystems up\n"
    )
    console.print(Panel.fit(next_steps, border_style="green"))
