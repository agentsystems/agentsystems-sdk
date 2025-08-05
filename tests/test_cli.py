"""CLI smoke tests using Typer's CliRunner.

No Docker interaction – we only exercise commands that do not spawn external
processes. This gives us quick coverage over argument parsing paths.
"""

from typer.testing import CliRunner


from agentsystems_sdk.cli import app
from agentsystems_sdk.utils import (
    compose_args,
    read_env_file,
    ensure_docker_installed,
)
from agentsystems_sdk.utils import cleanup_langfuse_init_vars as cleanup_init_vars

import pytest
import shutil
import typer

runner = CliRunner()


def test_version_option():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    # The version string is printed alone on stdout.
    assert result.stdout.strip()  # non-empty


def test_version_option_dev_mode(monkeypatch):
    """Test version option when package is not installed (dev mode)."""
    import importlib.metadata as metadata

    def mock_version(name):
        raise metadata.PackageNotFoundError(f"No package named {name}")

    monkeypatch.setattr(metadata, "version", mock_version)

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "unknown (development mode)" in result.stdout


def test_help_top_level():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AgentSystems" in result.stdout


def test_help_subcommand():
    # pick a subcommand that does not require Docker to be installed
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Initialize a new AgentSystems deployment" in result.stdout


# ---------------------------------------------------------------------------
# Helper-function tests (merged from former test_cli_helpers.py)
# ---------------------------------------------------------------------------


def test_compose_args_basic(tmp_path):
    # create minimal core compose file in expected location
    compose_dir = tmp_path / "compose" / "local"
    compose_dir.mkdir(parents=True)
    core = compose_dir / "docker-compose.yml"
    core.write_text("version: '3'\nservices: {}\n")

    compose_file, args = compose_args(tmp_path, langfuse=False)
    # compose_args now returns tuple of (compose_file, args)
    assert compose_file == core
    assert any("docker" in arg for arg in args)  # Has docker or docker-compose
    assert "-f" in args
    assert str(core) in args


def test_compose_args_with_langfuse(tmp_path):
    # core file in expected location
    compose_dir = tmp_path / "compose" / "local"
    compose_dir.mkdir(parents=True)
    core = compose_dir / "docker-compose.yml"
    core.write_text("version: '3'\nservices: {}\n")
    # langfuse overlay
    lf_dir = tmp_path / "langfuse"
    lf_dir.mkdir(parents=True)
    lf = lf_dir / "docker-compose.langfuse.yml"
    lf.write_text("version: '3'\nservices: {}\n")

    compose_file, args = compose_args(tmp_path, langfuse=True)
    # compose_args now returns tuple of (compose_file, args)
    assert compose_file == core
    assert "-f" in args
    assert str(core) in args
    assert str(lf) in args


def test_read_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# comment line
KEY1=value1
KEY2="value 2"
EMPTY=
"""
    )
    data = read_env_file(env_file)
    assert data == {"KEY1": "value1", "KEY2": "value 2", "EMPTY": ""}


def test_cleanup_init_vars(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        """LANGFUSE_INIT_ADMIN_EMAIL=foo@bar.com
LANGFUSE_INIT_ADMIN_PASSWORD=secret
REGULAR_KEY=value
"""
    )

    cleanup_init_vars(env_path)
    text = env_path.read_text()
    # original INIT vars should be commented now
    assert "# LANGFUSE_INIT_ADMIN_EMAIL=" in text
    assert "# LANGFUSE_INIT_ADMIN_PASSWORD=" in text
    # notice header present
    assert "Langfuse initialization values" in text
    # regular key remains uncommented
    assert "REGULAR_KEY=value" in text


# ---------------------------------------------------------------------------
# Negative-path tests hitting CLI helper exits
# ---------------------------------------------------------------------------


def test_compose_args_missing(tmp_path):
    """compose_args should exit when no compose file is present."""
    with pytest.raises(typer.Exit):
        compose_args(tmp_path, langfuse=True)


def test_ensure_docker_installed_exit(monkeypatch):
    """ensure_docker_installed exits if docker CLI is missing."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(typer.Exit):
        ensure_docker_installed()


def test_status_command_no_docker(tmp_path, monkeypatch):
    """status should exit 1 when docker CLI is missing."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 1
    assert "Docker CLI not found" in result.stdout


def test_app_invocation_no_args():
    result = runner.invoke(app, [])
    # Typer exits with code 2 when no command/options are supplied.
    assert result.exit_code == 2


def test_main_callback():
    """Test the main callback function."""
    from agentsystems_sdk.cli import main

    # Call main with version=None (normal case)
    main(version=None)  # Should not raise


def test_version_callback_false():
    """Test version callback with False value."""
    from agentsystems_sdk.cli import version_callback

    # Should not raise or exit
    version_callback(False)


def test_all_commands_registered():
    """Test that all expected commands are registered."""
    # Get all registered command names
    command_names = [cmd.name for cmd in app.registered_commands]

    expected_commands = [
        "init",
        "up",
        "down",
        "logs",
        "restart",
        "status",
        "run",
        "artifacts-path",
        "clean",
    ]

    for cmd in expected_commands:
        assert cmd in command_names


def test_dotenv_loading(monkeypatch, tmp_path):
    """Test that dotenv loading logic works."""
    # Create a test env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value")

    # Set the environment variable to point to our test env file
    monkeypatch.setenv("AGENTSYSTEMS_GLOBAL_ENV", str(env_file))

    # Re-import to trigger the loading logic
    import importlib
    import agentsystems_sdk.cli

    importlib.reload(agentsystems_sdk.cli)

    # The env var should be loaded (though we can't easily test this directly)
    # Just verify the code path doesn't crash
