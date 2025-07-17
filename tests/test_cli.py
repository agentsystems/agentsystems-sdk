"""CLI smoke tests using Typer's CliRunner.

No Docker interaction – we only exercise commands that do not spawn external
processes. This gives us quick coverage over argument parsing paths.
"""

from typer.testing import CliRunner


from agentsystems_sdk.cli import (
    app,
    _compose_args,
    _read_env_file,
    _cleanup_init_vars,
    _ensure_docker_installed,
)

import pytest
import shutil
import typer

runner = CliRunner()


def test_version_option():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    # The version string is printed alone on stdout.
    assert result.stdout.strip()  # non-empty


def test_help_top_level():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AgentSystems" in result.stdout


def test_help_subcommand():
    # pick a subcommand that does not require Docker to be installed
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Clone the agent deployment template" in result.stdout


# ---------------------------------------------------------------------------
# Helper-function tests (merged from former test_cli_helpers.py)
# ---------------------------------------------------------------------------


def test_compose_args_basic(tmp_path):
    # create minimal core compose file
    core = tmp_path / "docker-compose.yml"
    core.write_text("version: '3'\nservices: {}\n")

    c_path, args = _compose_args(tmp_path, no_langfuse=True)
    assert c_path == core
    assert args == ["-f", str(core)]


def test_compose_args_with_langfuse(tmp_path):
    # core file
    core = tmp_path / "docker-compose.yml"
    core.write_text("version: '3'\nservices: {}\n")
    # langfuse overlay
    lf_dir = tmp_path / "compose" / "langfuse"
    lf_dir.mkdir(parents=True)
    lf = lf_dir / "docker-compose.yml"
    lf.write_text("version: '3'\nservices: {}\n")

    _c_path, args = _compose_args(tmp_path, no_langfuse=False)
    assert args == ["-f", str(core), "-f", str(lf)]


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
    data = _read_env_file(env_file)
    assert data == {"KEY1": "value1", "KEY2": "value 2", "EMPTY": ""}


def test_cleanup_init_vars(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        """LANGFUSE_INIT_ADMIN_EMAIL=foo@bar.com
LANGFUSE_INIT_ADMIN_PASSWORD=secret
REGULAR_KEY=value
"""
    )

    _cleanup_init_vars(env_path)
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
    """_compose_args should exit when no compose file is present."""
    with pytest.raises(typer.Exit):
        _compose_args(tmp_path, no_langfuse=True)


def test_ensure_docker_installed_exit(monkeypatch):
    """_ensure_docker_installed exits if docker CLI is missing."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(typer.Exit):
        _ensure_docker_installed()


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
