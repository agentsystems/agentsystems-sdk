"""Tests for the restart command."""

from unittest.mock import patch

from agentsystems_sdk.commands.restart import restart_command
from agentsystems_sdk.commands.up import AgentStartMode


class TestRestartCommand:
    """Tests for the restart command."""

    @patch("agentsystems_sdk.commands.restart.up_command")
    def test_restart_calls_up(
        self,
        mock_up_command,
        tmp_path,
    ):
        """Test restart command calls up (which handles down → up sequence)."""
        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,
            wait_ready=True,
            no_langfuse=False,
            agents_mode=AgentStartMode.create,
            env_file=None,
        )

        # Verify up was called (up now handles down internally)
        mock_up_command.assert_called_once_with(
            project_dir=tmp_path,
            detach=True,
            fresh=False,
            wait_ready=True,
            no_langfuse=False,
            agents_mode=AgentStartMode.create,
            env_file=None,
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

    @patch("agentsystems_sdk.commands.restart.up_command")
    def test_restart_passes_options_correctly(
        self,
        mock_up_command,
        tmp_path,
    ):
        """Test restart command passes options to up correctly."""
        # Execute with specific options
        restart_command(
            project_dir=tmp_path,
            detach=False,  # Foreground
            wait_ready=False,  # No wait
            no_langfuse=True,  # No Langfuse
            agents_mode=AgentStartMode.all,  # Start all agents
            env_file=tmp_path / ".env.test",
        )

        # Verify options passed to up
        mock_up_command.assert_called_once_with(
            project_dir=tmp_path,
            detach=False,  # Passed through
            fresh=False,
            wait_ready=False,  # Passed through
            no_langfuse=True,  # Passed through
            agents_mode=AgentStartMode.all,  # Passed through
            env_file=tmp_path / ".env.test",  # Passed through
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

    @patch("agentsystems_sdk.commands.restart.up_command")
    def test_restart_up_failure_propagates(
        self,
        mock_up_command,
        tmp_path,
    ):
        """Test restart command propagates up command failures."""
        # Make up command fail
        import typer

        mock_up_command.side_effect = typer.Exit(code=1)

        # Execute and expect exception
        try:
            restart_command(
                project_dir=tmp_path,
                detach=True,
                wait_ready=True,
                no_langfuse=False,
                agents_mode=AgentStartMode.create,
                env_file=None,
            )
            assert False, "Expected typer.Exit to be raised"
        except typer.Exit as e:
            assert e.exit_code == 1

        # Verify up was called
        mock_up_command.assert_called_once()
