"""Tests for the clean command."""

from unittest.mock import patch

import typer

from agentsystems_sdk.commands.clean import clean_command


class TestCleanCommand:
    """Tests for the clean command."""

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.clean.console.print")
    def test_clean_command_basic(
        self,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test basic clean command with default options."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        clean_command(
            project_dir=tmp_path,
            prune_system=True,  # Default
            no_langfuse=False,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=True)

        # Verify commands were run
        assert mock_run_command.call_count == 2

        # First call: docker-compose down -v
        down_call = mock_run_command.call_args_list[0]
        cmd = down_call[0][0]
        assert "down" in cmd
        assert "-v" in cmd

        # Second call: docker system prune -f
        prune_call = mock_run_command.call_args_list[1]
        cmd = prune_call[0][0]
        assert cmd == ["docker", "system", "prune", "-f"]

        # Verify console messages
        print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any("Removing containers and volumes" in call for call in print_calls)
        assert any("Pruning Docker system" in call for call in print_calls)
        assert any("Cleanup complete" in call for call in print_calls)

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    def test_clean_command_no_prune(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test clean command with --no-prune-system option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        clean_command(
            project_dir=tmp_path,
            prune_system=False,
            no_langfuse=False,
        )

        # Verify only down command was run (no prune)
        assert mock_run_command.call_count == 1
        cmd = mock_run_command.call_args[0][0]
        assert "down" in cmd
        assert "-v" in cmd

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    def test_clean_command_no_langfuse(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test clean command with --no-langfuse option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        clean_command(
            project_dir=tmp_path,
            prune_system=True,
            no_langfuse=True,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.clean.console.print")
    def test_clean_command_prune_failure(
        self,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test clean command handles prune failure gracefully."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Make prune command fail
        def run_command_side_effect(cmd, env):
            if "prune" in cmd:
                raise Exception("Prune failed")

        mock_run_command.side_effect = run_command_side_effect

        # Execute
        clean_command(
            project_dir=tmp_path,
            prune_system=True,
            no_langfuse=False,
        )

        # Verify both commands were attempted
        assert mock_run_command.call_count == 2

        # Verify warning message was shown
        print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any("Docker prune failed (non-fatal)" in call for call in print_calls)
        assert any("Cleanup complete" in call for call in print_calls)

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.clean.os.environ.copy")
    def test_clean_command_environment_handling(
        self,
        mock_environ_copy,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test clean command passes environment correctly."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        test_env = {"TEST_VAR": "test_value", "PATH": "/usr/bin"}
        mock_environ_copy.return_value = test_env

        # Execute
        clean_command(
            project_dir=tmp_path,
            prune_system=True,
            no_langfuse=False,
        )

        # Verify environment was copied and passed to commands
        mock_environ_copy.assert_called_once()

        # Check both command calls used the environment
        for call in mock_run_command.call_args_list:
            assert call[0][1] == test_env

    @patch("agentsystems_sdk.commands.clean.run_command_with_env")
    @patch("agentsystems_sdk.commands.clean.compose_args")
    @patch("agentsystems_sdk.commands.clean.ensure_docker_installed")
    def test_clean_command_compose_down_failure(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test clean command when docker-compose down fails."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Make down command fail
        mock_run_command.side_effect = typer.Exit(code=1)

        # Execute and expect exception
        try:
            clean_command(
                project_dir=tmp_path,
                prune_system=True,
                no_langfuse=False,
            )
        except typer.Exit as e:
            assert e.exit_code == 1

        # Verify only one command was attempted (failed on down)
        assert mock_run_command.call_count == 1
