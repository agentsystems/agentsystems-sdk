"""Test update command functionality."""

from unittest.mock import patch

import typer
from typer.testing import CliRunner

from agentsystems_sdk.commands.update import update_command


class TestUpdateCommand:
    """Test cases for the update command."""

    def test_update_command_help(self):
        """Test update command help output."""
        runner = CliRunner()
        result = runner.invoke(update_command, ["--help"])
        assert result.exit_code == 0
        assert "Update core AgentSystems platform images" in result.output

    def test_update_command_no_config_file(self, tmp_path):
        """Test update command fails when no config file exists."""
        runner = CliRunner()
        result = runner.invoke(update_command, [str(tmp_path)])
        assert result.exit_code == 1
        assert "No agentsystems-config.yml found" in result.output

    @patch("agentsystems_sdk.commands.update.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.update.run_command")
    def test_update_command_success(
        self, mock_run_command, mock_ensure_docker, tmp_path
    ):
        """Test successful update command execution."""
        # Create a minimal config file
        config_file = tmp_path / "agentsystems-config.yml"
        config_file.write_text("config_version: 1\n")

        runner = CliRunner()
        result = runner.invoke(update_command, [str(tmp_path)])

        assert result.exit_code == 0
        assert "Updating AgentSystems core platform images" in result.output
        assert "Core platform images updated successfully" in result.output

        # Verify docker pull commands were called
        expected_calls = [
            ["docker", "pull", "ghcr.io/agentsystems/agent-control-plane:latest"],
            ["docker", "pull", "ghcr.io/agentsystems/agentsystems-ui:latest"],
        ]
        actual_calls = [call[0][0] for call in mock_run_command.call_args_list]
        assert mock_run_command.call_count == 2
        assert actual_calls == expected_calls

    @patch("agentsystems_sdk.commands.update.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.update.run_command")
    def test_update_command_docker_fail(
        self, mock_run_command, mock_ensure_docker, tmp_path
    ):
        """Test update command handles docker pull failures."""
        # Create a minimal config file
        config_file = tmp_path / "agentsystems-config.yml"
        config_file.write_text("config_version: 1\n")

        # Simulate docker pull failure
        mock_run_command.side_effect = typer.Exit(code=1)

        runner = CliRunner()
        result = runner.invoke(update_command, [str(tmp_path)])

        assert result.exit_code == 1

    def test_update_command_current_directory(self, tmp_path, monkeypatch):
        """Test update command uses current directory when no path provided."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create a minimal config file
        config_file = tmp_path / "agentsystems-config.yml"
        config_file.write_text("config_version: 1\n")

        with (
            patch("agentsystems_sdk.commands.update.ensure_docker_installed"),
            patch("agentsystems_sdk.commands.update.run_command") as mock_run,
        ):

            runner = CliRunner()
            result = runner.invoke(update_command, [])

            assert result.exit_code == 0
            assert mock_run.call_count == 2  # Two images pulled
