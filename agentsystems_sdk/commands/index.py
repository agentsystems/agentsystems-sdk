"""Index commands for managing agents in the AgentSystems Index."""

from __future__ import annotations

import pathlib

import typer
import yaml
from rich.console import Console

console = Console()

# Create index sub-app
index_commands = typer.Typer(
    name="index",
    help="Manage agents in the AgentSystems community index",
    no_args_is_help=True,
)


@index_commands.command(name="validate")
def validate_command() -> None:
    """Validate profile.yaml and agent YAML files in the current directory.

    Run this from your developer folder in a forked agent-index repository:

        agent-index/developers/yourname/
            profile.yaml
            agents/
                agent1.yaml
                agent2.yaml

    This validates your files before submitting a pull request.
    """
    current_dir = pathlib.Path.cwd()

    # Check for profile.yaml
    profile_path = current_dir / "profile.yaml"
    if not profile_path.exists():
        console.print("[red]✗[/red] No profile.yaml found in current directory.")
        console.print("\nExpected directory structure:")
        console.print("  agent-index/developers/yourname/")
        console.print("    profile.yaml")
        console.print("    agents/")
        console.print("      agent1.yaml")
        console.print("      agent2.yaml")
        console.print("\nRun this command from your developer folder.")
        raise typer.Exit(1)

    # Track validation status
    has_errors = False

    console.print("\n[cyan]Validating developer profile...[/cyan]\n")

    # Load and validate profile.yaml
    try:
        with profile_path.open("r") as f:
            profile_data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read profile.yaml: {e}")
        raise typer.Exit(1)

    # Validate required fields
    profile_required_fields = ["name", "developer"]
    for field in profile_required_fields:
        if field in profile_data and profile_data[field]:
            console.print(f"[green]✓[/green] {field}: {profile_data[field]}")
        else:
            console.print(f"[red]✗[/red] {field}: missing or empty")
            has_errors = True

    # Validate developer field matches folder name
    folder_name = current_dir.name
    if profile_data.get("developer") != folder_name:
        console.print(
            f"[red]✗[/red] Developer field '{profile_data.get('developer')}' does not match folder name '{folder_name}'"
        )
        has_errors = True
    else:
        console.print("[green]✓[/green] Developer field matches folder name")

    # Optional fields
    profile_optional_fields = [
        "type",
        "avatar_url",
        "bio",
        "tagline",
        "company",
        "location",
        "years_experience",
        "website",
        "support_email",
        "documentation_url",
        "twitter_handle",
        "linkedin_url",
        "discord_username",
        "expertise",
        "featured_work",
        "open_to_collaboration",
        "sponsor_url",
    ]

    console.print("\n[cyan]Optional profile fields:[/cyan]")
    for field in profile_optional_fields:
        value = profile_data.get(field)
        if value:
            if isinstance(value, list):
                console.print(f"  {field}: {', '.join(str(v) for v in value)}")
            else:
                console.print(f"  {field}: {value}")

    # Check for agents directory
    agents_dir = current_dir / "agents"
    if not agents_dir.exists() or not agents_dir.is_dir():
        console.print("\n[yellow]⚠[/yellow] No agents/ directory found")
        console.print("  Create agents/ directory and add your agent YAML files")
    else:
        # Validate all agent YAML files
        agent_files = list(agents_dir.glob("*.yaml"))

        if not agent_files:
            console.print("\n[yellow]⚠[/yellow] No agent YAML files found in agents/")
        else:
            console.print(
                f"\n[cyan]Validating {len(agent_files)} agent file(s)...[/cyan]\n"
            )

            for agent_file in agent_files:
                console.print(f"[bold]{agent_file.name}[/bold]")

                try:
                    with agent_file.open("r") as f:
                        agent_data = yaml.safe_load(f)
                except Exception as e:
                    console.print(
                        f"  [red]✗[/red] Failed to read {agent_file.name}: {e}"
                    )
                    has_errors = True
                    continue

                # Validate required fields
                agent_required_fields = [
                    "name",
                    "developer",
                    "version",
                    "description",
                    "model_dependencies",
                ]
                for field in agent_required_fields:
                    if field in agent_data and agent_data[field]:
                        if field == "model_dependencies":
                            console.print(
                                f"  [green]✓[/green] {field}: {', '.join(agent_data[field])}"
                            )
                        else:
                            console.print(
                                f"  [green]✓[/green] {field}: {agent_data[field]}"
                            )
                    else:
                        console.print(f"  [red]✗[/red] {field}: missing or empty")
                        has_errors = True

                # Validate developer field matches folder name
                if agent_data.get("developer") != folder_name:
                    console.print(
                        f"  [red]✗[/red] Agent developer field '{agent_data.get('developer')}' does not match folder name '{folder_name}'"
                    )
                    has_errors = True

                # Check optional fields
                agent_optional_fields = [
                    "context",
                    "primary_function",
                    "readiness_level",
                    "listing_status",
                    "image_repository_url",
                    "image_repository_access",
                    "source_repository_url",
                    "source_repository_access",
                ]

                optional_count = sum(
                    1 for f in agent_optional_fields if agent_data.get(f)
                )
                if optional_count > 0:
                    console.print(
                        f"  [dim]+ {optional_count} optional field(s) set[/dim]"
                    )

                console.print()

    # Final status
    if has_errors:
        console.print("[red]✗[/red] Validation failed - fix errors above\n")
        raise typer.Exit(1)
    else:
        console.print("[green]✓[/green] Validation passed\n")
        console.print("Next steps:")
        console.print(
            "  1. Commit your changes: [cyan]git add . && git commit -m 'Add agent'[/cyan]"
        )
        console.print("  2. Push to your fork: [cyan]git push origin main[/cyan]")
        console.print("  3. Create a pull request to agentsystems/agent-index")
        console.print(
            "  4. GitHub Actions will validate and auto-merge if checks pass\n"
        )
