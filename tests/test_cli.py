"""CLI smoke tests using Typer's CliRunner.

No Docker interaction – we only exercise commands that do not spawn external
processes. This gives us quick coverage over argument parsing paths.
"""

from typer.testing import CliRunner

from agentsystems_sdk.cli import app

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
