"""Hub commands for publishing and managing agents in the AgentSystems Hub."""

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

# Create hub sub-app
hub_commands = typer.Typer(
    name="hub",
    help="Publish and manage agents in the AgentSystems Hub",
    no_args_is_help=True,
)

# Config file for storing API key
CONFIG_DIR = pathlib.Path.home() / ".agentsystems"
HUB_CONFIG_FILE = CONFIG_DIR / "hub-config.yml"
DEFAULT_HUB_URL = "http://localhost:8000"


def get_hub_config() -> dict:
    """Load hub configuration from file."""
    if not HUB_CONFIG_FILE.exists():
        return {}
    with HUB_CONFIG_FILE.open("r") as f:
        return yaml.safe_load(f) or {}


def save_hub_config(config: dict) -> None:
    """Save hub configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with HUB_CONFIG_FILE.open("w") as f:
        yaml.safe_dump(config, f)


def get_api_key() -> Optional[str]:
    """Get API key from config or environment."""
    # Check environment first
    api_key = os.getenv("AGENTSYSTEMS_HUB_API_KEY")
    if api_key:
        return api_key

    # Check config file
    config = get_hub_config()
    return config.get("api_key")


def get_hub_url() -> str:
    """Get hub URL from config or environment."""
    # Check environment first
    hub_url = os.getenv("AGENTSYSTEMS_HUB_URL")
    if hub_url:
        return hub_url

    # Check config file
    config = get_hub_config()
    return config.get("hub_url", DEFAULT_HUB_URL)


def get_developer_name() -> Optional[str]:
    """Get cached developer name from config."""
    config = get_hub_config()
    return config.get("developer_name")


@hub_commands.command(name="login")
def login_command(
    api_key: str = typer.Option(
        ..., prompt="Hub API key", hide_input=True, help="Your AgentSystems Hub API key"
    ),
    hub_url: str = typer.Option(DEFAULT_HUB_URL, help="Hub API URL"),
) -> None:
    """Store your AgentSystems Hub API key for publishing agents."""

    # Verify the API key works
    try:
        response = requests.get(
            f"{hub_url}/auth/verify",
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
        config = get_hub_config()
        config["api_key"] = api_key
        config["hub_url"] = hub_url
        config["user_uid"] = data.get("user_uid")
        config["developer_name"] = data.get("developer_name")
        config["email"] = data.get("email")
        config["api_key_label"] = data.get("api_key_label")
        save_hub_config(config)

        console.print(f"\n[green]✓[/green] API key saved to {HUB_CONFIG_FILE}")

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            console.print("[red]✗[/red] Invalid API key")
        else:
            console.print(f"[red]✗[/red] HTTP error: {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@hub_commands.command(name="logout")
def logout_command() -> None:
    """Remove stored API key and credentials."""
    if not HUB_CONFIG_FILE.exists():
        console.print("[yellow]Not logged in.[/yellow]")
        return

    try:
        HUB_CONFIG_FILE.unlink()
        console.print("[green]✓[/green] Logged out successfully")
        console.print(f"[green]✓[/green] Removed {HUB_CONFIG_FILE}")
    except Exception as e:
        console.print(f"[red]✗[/red] Error removing config: {e}")
        raise typer.Exit(1)


@hub_commands.command(name="list")
def list_command() -> None:
    """List all your agents in the hub."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]✗[/red] Not logged in. Run 'agentsystems hub login' first.")
        raise typer.Exit(1)

    hub_url = get_hub_url()

    try:
        response = requests.get(
            f"{hub_url}/agents/me",
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
                "Publish your first agent with: [cyan]agentsystems hub publish[/cyan]"
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
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems hub login' again."
            )
        else:
            console.print(f"[red]✗[/red] HTTP error: {e.response.status_code}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@hub_commands.command(name="publish")
def publish_command() -> None:
    """Publish or update an agent in the hub from agent.yaml."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]✗[/red] Not logged in. Run 'agentsystems hub login' first.")
        raise typer.Exit(1)

    hub_url = get_hub_url()

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
            f"{hub_url}/auth/verify",
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
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems hub login' again."
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
    }

    # Show what will be published
    console.print("\n[cyan]Publishing agent with the following settings:[/cyan]")
    console.print(f"  Developer: {authenticated_developer}")
    console.print(f"  Name: {name}")
    console.print(f"  Description: {payload.get('description') or '(empty)'}")
    console.print(f"  Image URL: {payload.get('image_repository_url') or '(empty)'}")
    console.print(f"  Source URL: {payload.get('source_repository_url') or '(empty)'}")
    console.print(f"  Listing: {payload.get('listing_status')}")
    console.print(f"  Image Access: {payload.get('image_repository_access')}")
    console.print(f"  Source Access: {payload.get('source_repository_access')}")
    console.print()

    # Ask for confirmation
    confirm = typer.confirm("Publish this agent to the hub?")
    if not confirm:
        console.print("[yellow]Publish cancelled.[/yellow]")
        raise typer.Exit(0)

    try:
        # Try to create first
        response = requests.post(
            f"{hub_url}/agents",
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
                    f"{hub_url}/agents/{authenticated_developer}/{name}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0,
                )
                current_response.raise_for_status()
                current_agent = current_response.json()

                # Compare settings that will be overwritten
                changes = []
                fields_to_check = [
                    ("description", "Description"),
                    ("image_repository_url", "Image URL"),
                    ("source_repository_url", "Source URL"),
                    ("listing_status", "Listing Status"),
                    ("image_repository_access", "Image Access"),
                    ("source_repository_access", "Source Access"),
                ]

                for field, label in fields_to_check:
                    current_value = current_agent.get(field)
                    new_value = payload.get(field)
                    if current_value != new_value:
                        changes.append(
                            {
                                "label": label,
                                "current": current_value or "(empty)",
                                "new": new_value or "(empty)",
                            }
                        )

                if changes:
                    console.print(
                        "\n[yellow]Warning: Publishing will overwrite the following hub settings:[/yellow]"
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
                f"{hub_url}/agents/{authenticated_developer}/{name}",
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
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems hub login' again."
            )
        else:
            error_detail = e.response.json().get("detail", str(e))
            console.print(f"[red]✗[/red] Error: {error_detail}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@hub_commands.command(name="delete")
def delete_command(
    name: str = typer.Argument(..., help="Agent name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete an agent from the hub."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]✗[/red] Not logged in. Run 'agentsystems hub login' first.")
        raise typer.Exit(1)

    hub_url = get_hub_url()

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
                "[red]✗[/red] Developer name not found. Run 'agentsystems hub login' again."
            )
            raise typer.Exit(1)

        # Delete agent
        response = requests.delete(
            f"{hub_url}/agents/{developer_name}/{name}",
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
                "[red]✗[/red] Invalid or expired API key. Run 'agentsystems hub login' again."
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
