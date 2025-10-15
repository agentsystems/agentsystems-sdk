"""Index commands for publishing and managing agents in the AgentSystems Index."""

from __future__ import annotations

import os
import pathlib
from typing import Optional

import requests
import typer
import yaml
from rich.console import Console
from rich.table import Table

console = Console()

# Create index sub-app
index_commands = typer.Typer(
    name="index",
    help="Publish and manage agents in the AgentSystems Index",
    no_args_is_help=True,
)

# Config file for storing API key
CONFIG_DIR = pathlib.Path.home() / ".agentsystems"
INDEX_CONFIG_FILE = CONFIG_DIR / "index-config.yml"
DEFAULT_INDEX_URL = "https://index-api.agentsystems.ai"


def get_index_config() -> dict:
    """Load index configuration from file."""
    if not INDEX_CONFIG_FILE.exists():
        return {}
    with INDEX_CONFIG_FILE.open("r") as f:
        return yaml.safe_load(f) or {}


def save_index_config(config: dict) -> None:
    """Save index configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_CONFIG_FILE.open("w") as f:
        yaml.safe_dump(config, f)


def get_api_key() -> Optional[str]:
    """Get API key from config or environment."""
    # Check environment first
    api_key = os.getenv("AGENTSYSTEMS_INDEX_API_KEY")
    if api_key:
        return api_key

    # Check config file
    config = get_index_config()
    return config.get("api_key")


def get_index_url() -> str:
    """Get index URL from config or environment."""
    # Check environment first
    index_url = os.getenv("AGENTSYSTEMS_INDEX_URL")
    if index_url:
        return index_url

    # Check config file
    config = get_index_config()
    return config.get("index_url", DEFAULT_INDEX_URL)


def get_developer_name() -> Optional[str]:
    """Get cached developer name from config."""
    config = get_index_config()
    return config.get("developer_name")


@index_commands.command(name="login")
def login_command(
    api_key: str = typer.Option(
        ...,
        prompt="Index API key",
        hide_input=True,
        help="Your AgentSystems Index API key",
    ),
    index_url: str = typer.Option(DEFAULT_INDEX_URL, help="Index API URL"),
) -> None:
    """Store your AgentSystems Index API key for publishing agents."""

    # Verify the API key works
    try:
        response = requests.get(
            f"{index_url}/auth/verify",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        console.print(
            f"[green]✓[/green] Successfully authenticated as: {data.get('email')}"
        )
        console.print(f"[green]✓[/green] Developer name: {data.get('developer_name')}")

        # Save to config
        config = get_index_config()
        config["api_key"] = api_key
        config["index_url"] = index_url
        config["user_uid"] = data.get("user_uid")
        config["developer_name"] = data.get("developer_name")
        config["email"] = data.get("email")
        config["api_key_label"] = data.get("api_key_label")
        save_index_config(config)

        console.print(f"\n[green]✓[/green] API key saved to {INDEX_CONFIG_FILE}")

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print("[red]✗[/red] Invalid API key")
        else:
            console.print(f"[red]✗[/red] HTTP error: {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@index_commands.command(name="logout")
def logout_command() -> None:
    """Remove stored API key and credentials."""
    if not INDEX_CONFIG_FILE.exists():
        console.print("[yellow]Not logged in.[/yellow]")
        return

    try:
        INDEX_CONFIG_FILE.unlink()
        console.print("[green]✓[/green] Logged out successfully")
        console.print(f"[green]✓[/green] Removed {INDEX_CONFIG_FILE}")
    except Exception as e:
        console.print(f"[red]✗[/red] Error removing config: {e}")
        raise typer.Exit(1)


@index_commands.command(name="whoami")
def whoami_command() -> None:
    """Show current logged-in developer identity."""
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]✗[/red] Not logged in. Run 'agentsystems index login' first."
        )
        raise typer.Exit(1)

    index_url = get_index_url()

    try:
        response = requests.get(
            f"{index_url}/auth/verify",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        console.print("\n[cyan]Logged in as:[/cyan]")
        console.print(f"  Developer: {data.get('developer_name')}")
        console.print(f"  Email: {data.get('email')}")
        if data.get("api_key_label"):
            console.print(f"  API Key: {data.get('api_key_label')}")
        console.print(f"  Index URL: {index_url}")
        console.print()

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        else:
            console.print(f"[red]✗[/red] HTTP error: {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@index_commands.command(name="validate")
def validate_command() -> None:
    """Validate agent.yaml without publishing."""
    # Look for agent.yaml in current directory
    agent_yaml_path = pathlib.Path.cwd() / "agent.yaml"
    if not agent_yaml_path.exists():
        console.print("[red]✗[/red] No agent.yaml found in current directory.")
        raise typer.Exit(1)

    # Load agent.yaml
    try:
        with agent_yaml_path.open("r") as f:
            agent_config = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read agent.yaml: {e}")
        raise typer.Exit(1)

    console.print("\n[cyan]Validating agent.yaml...[/cyan]\n")

    # Track validation status
    has_errors = False

    # Validate required fields
    required_fields = ["developer", "name", "description"]
    for field in required_fields:
        if field in agent_config and agent_config[field]:
            console.print(f"[green]✓[/green] {field}: {agent_config[field]}")
        else:
            console.print(f"[red]✗[/red] {field}: missing or empty")
            has_errors = True

    # Optional fields
    optional_fields = [
        "version",
        "image_repository_url",
        "source_repository_url",
        "listing_status",
        "image_repository_access",
        "source_repository_access",
        "model_dependencies",
    ]

    console.print("\n[cyan]Optional fields:[/cyan]")
    for field in optional_fields:
        value = agent_config.get(field)
        if value:
            if isinstance(value, list):
                console.print(f"  {field}: {', '.join(value)}")
            else:
                console.print(f"  {field}: {value}")
        else:
            console.print(f"  {field}: (not set)")

    # Check developer name against authenticated user
    api_key = get_api_key()
    if api_key:
        index_url = get_index_url()
        try:
            response = requests.get(
                f"{index_url}/auth/verify",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            authenticated_developer = data.get("developer_name")

            console.print("\n[cyan]Developer verification:[/cyan]")
            if agent_config.get("developer") == authenticated_developer:
                console.print(
                    f"[green]✓[/green] Developer matches logged-in user: {authenticated_developer}"
                )
            else:
                console.print("[yellow]⚠[/yellow] Developer mismatch:")
                console.print(f"  agent.yaml has: {agent_config.get('developer')}")
                console.print(f"  Logged in as: {authenticated_developer}")
                console.print(
                    "  Update agent.yaml or login with the correct account to publish."
                )
        except Exception:
            console.print(
                "\n[yellow]⚠[/yellow] Could not verify developer (not logged in or API unavailable)"
            )
    else:
        console.print(
            "\n[yellow]⚠[/yellow] Not logged in - skipping developer verification"
        )

    # Final status
    console.print()
    if has_errors:
        console.print("[red]✗[/red] Validation failed - fix errors above")
        raise typer.Exit(1)
    else:
        console.print("[green]✓[/green] Validation passed")


@index_commands.command(name="list")
def list_command() -> None:
    """List all your agents in the index."""
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]✗[/red] Not logged in. Run 'agentsystems index login' first."
        )
        raise typer.Exit(1)

    index_url = get_index_url()

    try:
        response = requests.get(
            f"{index_url}/agents/me",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        agents = data.get("agents", [])
        total = data.get("total", 0)

        if not agents:
            console.print("\n[yellow]No agents found.[/yellow]")
            console.print(
                "Publish your first agent with: [cyan]agentsystems index publish[/cyan]"
            )
            return

        # Create table
        table = Table(
            title=f"Your Agents ({total})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Listing", justify="center")
        table.add_column("Image Access", justify="center")
        table.add_column("Source Access", justify="center")

        for agent in agents:
            listing_badge = (
                "✓ Listed" if agent["listing_status"] == "listed" else "✗ Unlisted"
            )
            listing_style = "green" if agent["listing_status"] == "listed" else "yellow"

            image_access = agent.get("image_repository_access", "private")
            source_access = agent.get("source_repository_access", "private")

            table.add_row(
                agent["name"],
                agent.get("description", "")[:50]
                + ("..." if len(agent.get("description", "")) > 50 else ""),
                f"[{listing_style}]{listing_badge}[/{listing_style}]",
                image_access.capitalize(),
                source_access.capitalize(),
            )

        console.print("\n", table, "\n")

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        else:
            console.print(f"[red]✗[/red] HTTP error: {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@index_commands.command(name="publish")
def publish_command() -> None:
    """Publish or update an agent in the index from agent.yaml."""
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]✗[/red] Not logged in. Run 'agentsystems index login' first."
        )
        raise typer.Exit(1)

    index_url = get_index_url()

    # Look for agent.yaml in current directory
    agent_yaml_path = pathlib.Path.cwd() / "agent.yaml"
    if not agent_yaml_path.exists():
        console.print("[red]✗[/red] No agent.yaml found in current directory.")
        console.print("Run this command from your agent directory.")
        raise typer.Exit(1)

    # Load agent.yaml
    try:
        with agent_yaml_path.open("r") as f:
            agent_config = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read agent.yaml: {e}")
        raise typer.Exit(1)

    # Validate required fields
    required_fields = ["developer", "name", "description"]
    for field in required_fields:
        if field not in agent_config:
            console.print(f"[red]✗[/red] Missing required field in agent.yaml: {field}")
            raise typer.Exit(1)

    # Verify API key and get authenticated developer name (don't trust cached config)
    try:
        verify_response = requests.get(
            f"{index_url}/auth/verify",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        verify_response.raise_for_status()
        verify_data = verify_response.json()
        authenticated_developer = verify_data.get("developer_name")

        if not authenticated_developer:
            console.print("[red]✗[/red] Could not verify developer identity.")
            raise typer.Exit(1)
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        else:
            console.print(f"[red]✗[/red] Verification failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Verification error: {e}")
        raise typer.Exit(1)

    if agent_config["developer"] != authenticated_developer:
        console.print("[red]✗[/red] Developer mismatch!")
        console.print(f"  agent.yaml has: {agent_config['developer']}")
        console.print(f"  Logged in as: {authenticated_developer}")
        console.print("\nUpdate agent.yaml or login with the correct account.")
        raise typer.Exit(1)

    name = agent_config["name"]

    # Build request payload
    payload = {
        "name": name,
        "description": agent_config.get("description"),
        "image_repository_url": agent_config.get("image_repository_url"),
        "source_repository_url": agent_config.get("source_repository_url"),
        "listing_status": agent_config.get("listing_status", "unlisted"),
        "image_repository_access": agent_config.get(
            "image_repository_access", "private"
        ),
        "source_repository_access": agent_config.get(
            "source_repository_access", "private"
        ),
        # New discovery & classification fields
        "context": agent_config.get("context"),
        "primary_function": agent_config.get("primary_function"),
        "readiness_level": agent_config.get("readiness_level"),
        # New compatibility requirements
        "model_requirements": agent_config.get("model_requirements", []),
        "required_integrations": agent_config.get("required_integrations", []),
        "required_egress": agent_config.get("required_egress", []),
        "input_types": agent_config.get("input_types", []),
        "output_types": agent_config.get("output_types", []),
        "input_schema": agent_config.get("input_schema", {}),
        # Flexible metadata
        "facets": agent_config.get("facets", {}),
    }

    # Validate listing requirements
    if payload.get("listing_status") == "listed":
        if payload.get("image_repository_access") != "public":
            console.print("\n[red]✗[/red] Validation Error:")
            console.print("  Listed agents must have public image repository access.")
            console.print(
                "  Set image_repository_access: 'public' in agent.yaml to list this agent."
            )
            console.print(
                "\n  Note: The AgentSystems public index requires all listed agents to be"
            )
            console.print(
                "  immediately installable. Private images can only be published as unlisted."
            )
            raise typer.Exit(1)

    # Show what will be published
    console.print("\n[cyan]Publishing agent with the following settings:[/cyan]")
    console.print(f"  Developer: {authenticated_developer}")
    console.print(f"  Name: {name}")
    console.print(f"  Description: {payload.get('description') or '(empty)'}")
    console.print(f"  Context: {payload.get('context') or '(not set)'}")
    console.print(
        f"  Primary Function: {payload.get('primary_function') or '(not set)'}"
    )
    console.print(f"  Readiness: {payload.get('readiness_level') or '(not set)'}")
    console.print(f"  Image URL: {payload.get('image_repository_url') or '(empty)'}")
    console.print(f"  Source URL: {payload.get('source_repository_url') or '(empty)'}")
    console.print(f"  Listing: {payload.get('listing_status')}")
    console.print(f"  Image Access: {payload.get('image_repository_access')}")
    console.print(f"  Source Access: {payload.get('source_repository_access')}")
    if payload.get("model_requirements"):
        console.print(
            f"  Model Requirements: {len(payload['model_requirements'])} provider(s)"
        )
    if payload.get("required_integrations"):
        console.print(
            f"  Required Integrations: {len(payload['required_integrations'])} integration(s)"
        )
    if payload.get("input_schema"):
        console.print(f"  Input Schema: {len(payload['input_schema'])} field(s)")
    console.print()

    # Ask for confirmation
    confirm = typer.confirm("Publish this agent to the index?")
    if not confirm:
        console.print("[yellow]Publish cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        # Try to create first
        response = requests.post(
            f"{index_url}/agents",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=10.0,
        )

        if response.status_code == 409:
            # Agent exists, fetch current settings and compare
            console.print(f"[yellow]Agent '{name}' already exists.[/yellow]")

            # Fetch current agent settings
            try:
                current_response = requests.get(
                    f"{index_url}/agents/{authenticated_developer}/{name}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                current_response.raise_for_status()
                current_agent = current_response.json()

                # Compare all payload fields against current agent
                # Skip metadata fields that shouldn't trigger change detection
                fields_to_ignore = {
                    "name",  # Name is immutable
                    "id",
                    "developer_id",
                    "created_at",
                    "updated_at",
                }

                # Human-friendly labels for fields
                field_labels = {
                    "description": "Description",
                    "image_repository_url": "Image URL",
                    "source_repository_url": "Source URL",
                    "listing_status": "Listing Status",
                    "image_repository_access": "Image Access",
                    "source_repository_access": "Source Access",
                    "context": "Context",
                    "primary_function": "Primary Function",
                    "readiness_level": "Readiness Level",
                    "model_requirements": "Model Requirements",
                    "required_integrations": "Required Integrations",
                    "required_egress": "Required Egress",
                    "input_types": "Input Types",
                    "output_types": "Output Types",
                    "input_schema": "Input Schema",
                    "facets": "Facets",
                }

                changes = []
                for field, new_value in payload.items():
                    if field in fields_to_ignore:
                        continue

                    current_value = current_agent.get(field)

                    # Deep comparison for lists and dicts
                    if current_value != new_value:
                        # Format lists and dicts nicely for display
                        if isinstance(current_value, list):
                            current_display = (
                                ", ".join(str(v) for v in current_value)
                                if current_value
                                else "(empty)"
                            )
                        elif isinstance(current_value, dict):
                            current_display = (
                                f"{len(current_value)} item(s)"
                                if current_value
                                else "(empty)"
                            )
                        else:
                            current_display = current_value or "(empty)"

                        if isinstance(new_value, list):
                            new_display = (
                                ", ".join(str(v) for v in new_value)
                                if new_value
                                else "(empty)"
                            )
                        elif isinstance(new_value, dict):
                            new_display = (
                                f"{len(new_value)} item(s)" if new_value else "(empty)"
                            )
                        else:
                            new_display = new_value or "(empty)"

                        # Use friendly label if available, otherwise use field name with title case
                        label = field_labels.get(field, field.replace("_", " ").title())

                        changes.append(
                            {
                                "label": label,
                                "current": current_display,
                                "new": new_display,
                            }
                        )

                if changes:
                    console.print(
                        "\n[yellow]Warning: Publishing will overwrite the following index settings:[/yellow]"
                    )
                    for change in changes:
                        console.print(
                            f"  - {change['label']}: {change['current']} → {change['new']}"
                        )
                    console.print()

                    # Ask for confirmation
                    confirm = typer.confirm("Continue with publish?")
                    if not confirm:
                        console.print("[yellow]Publish cancelled.[/yellow]")
                        raise typer.Exit(0)
                else:
                    console.print("[green]No changes detected. Updating...[/green]")

            except requests.HTTPError as e:
                console.print(
                    f"[yellow]Could not fetch current agent settings: {e}[/yellow]"
                )
                console.print("[yellow]Proceeding with update...[/yellow]")

            # Update agent
            response = requests.put(
                f"{index_url}/agents/{authenticated_developer}/{name}",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=10.0,
            )

        response.raise_for_status()
        agent = response.json()

        console.print(
            f"\n[green]✓[/green] Successfully published agent: [cyan]{agent['name']}[/cyan]"
        )
        if agent.get("description"):
            console.print(f"  Description: {agent['description']}")
        if agent.get("image_repository_url"):
            console.print(f"  Image: {agent['image_repository_url']}")
        if agent.get("source_repository_url"):
            console.print(f"  Source: {agent['source_repository_url']}")
        console.print(
            f"  Listing: {'Listed (public)' if agent['listing_status'] == 'listed' else 'Unlisted (private)'}"
        )

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        else:
            error_detail = e.response.json().get("detail", str(e))

            # Special handling for listed agents error
            if "Listed agents not enabled" in error_detail:
                console.print(
                    "[red]✗[/red] Error: Listed agents disabled for this developer"
                )
                console.print(
                    "To publish as listed, run: [cyan]agentsystems index allow-listed --enable[/cyan]"
                )
            else:
                console.print(f"[red]✗[/red] Error: {error_detail}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@index_commands.command(name="delete")
def delete_command(
    name: str = typer.Argument(..., help="Agent name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete an agent from the index."""
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]✗[/red] Not logged in. Run 'agentsystems index login' first."
        )
        raise typer.Exit(1)

    index_url = get_index_url()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete '{name}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        # Get developer name from cache
        developer_name = get_developer_name()
        if not developer_name:
            console.print(
                "[red]✗[/red] Developer name not found. Run 'agentsystems index login' again."
            )
            raise typer.Exit(1)

        # Delete agent
        response = requests.delete(
            f"{index_url}/agents/{developer_name}/{name}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()

        console.print(
            f"[green]✓[/green] Successfully deleted agent: [cyan]{name}[/cyan]"
        )

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        elif e.response.status_code == 404:
            console.print(f"[red]✗[/red] Agent '{name}' not found")
        else:
            error_detail = e.response.json().get("detail", str(e))
            console.print(f"[red]✗[/red] Error: {error_detail}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@index_commands.command(name="allow-listed")
def allow_listed_command(
    enable: bool = typer.Option(False, "--enable", help="Enable listed agents"),
    disable: bool = typer.Option(False, "--disable", help="Disable listed agents"),
    cascade: bool = typer.Option(
        False, "--cascade", help="When disabling, unlist all existing agents"
    ),
    preserve: bool = typer.Option(
        False, "--preserve", help="When disabling, keep existing agents as-is"
    ),
) -> None:
    """Enable or disable listed agents for your developer account."""
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]✗[/red] Not logged in. Run 'agentsystems index login' first."
        )
        raise typer.Exit(1)

    index_url = get_index_url()

    # Validate flags
    if enable and disable:
        console.print("[red]✗[/red] Cannot use both --enable and --disable")
        raise typer.Exit(1)

    if not enable and not disable:
        console.print("[red]✗[/red] Must specify either --enable or --disable")
        raise typer.Exit(1)

    if enable and (cascade or preserve):
        console.print("[red]✗[/red] --cascade and --preserve only apply when disabling")
        raise typer.Exit(1)

    if disable and not (cascade or preserve):
        console.print(
            "[red]✗[/red] When disabling, must specify either --cascade or --preserve"
        )
        raise typer.Exit(1)

    if cascade and preserve:
        console.print("[red]✗[/red] Cannot use both --cascade and --preserve")
        raise typer.Exit(1)

    try:
        # Update developer settings
        response = requests.patch(
            f"{index_url}/developers/me",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"allow_listed_agents": enable},
            timeout=10.0,
        )
        response.raise_for_status()

        if enable:
            console.print("[green]✓[/green] Listed agents enabled")
            console.print("  Agents can now be published with listing_status: listed")
        else:
            if cascade:
                # Unlist all existing agents
                unlist_response = requests.post(
                    f"{index_url}/developers/me/unlist-all",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                unlist_response.raise_for_status()
                unlist_data = unlist_response.json()
                unlisted_count = unlist_data.get("unlisted_count", 0)

                console.print("[green]✓[/green] Listed agents disabled")
                console.print(f"  Unlisted {unlisted_count} agent(s)")
            else:  # preserve
                console.print("[green]✓[/green] Listed agents disabled")
                console.print("  Existing listed agents remain listed")
                console.print("  New agents cannot be published as listed")

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print(
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems index login' again."
            )
        else:
            error_detail = e.response.json().get("detail", str(e))
            console.print(f"[red]✗[/red] Error: {error_detail}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)
