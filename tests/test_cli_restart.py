"""Tests for the restart command."""

from unittest.mock import patch

from agentsystems_sdk.commands.restart import restart_command


class TestRestartCommand:
    """Tests for the restart command."""

    @patch("agentsystems_sdk.commands.restart.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.restart.console.print")
    @patch("agentsystems_sdk.commands.restart.os.environ.copy")
    def test_restart_command_detached_with_wait(
        self,
        mock_environ_copy,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        tmp_path,
    ):
        """Test restart command in detached mode with wait (default)."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        test_env = {"TEST_VAR": "test_value"}
        mock_environ_copy.return_value = test_env
        mock_wait_gateway.return_value = True

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,  # Default
            wait_ready=True,  # Default
            no_langfuse=False,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=True)

        # Verify two commands were run (down, then up)
        assert mock_run_command.call_count == 2

        # First call: docker-compose down
        down_call = mock_run_command.call_args_list[0]
        down_cmd = down_call[0][0]
        assert "down" in down_cmd
        assert down_call[0][1] == test_env

        # Second call: docker-compose up -d
        up_call = mock_run_command.call_args_list[1]
        up_cmd = up_call[0][0]
        assert "up" in up_cmd
        assert "-d" in up_cmd
        assert up_call[0][1] == test_env

        # Verify gateway wait was called
        mock_wait_gateway.assert_called_once_with()

        # Verify console messages
        print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any("Stopping core services" in call for call in print_calls)
        assert any("Starting core services" in call for call in print_calls)
        assert any("Restart complete" in call for call in print_calls)

    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_foreground(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test restart command in foreground mode."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=False,  # Foreground
            wait_ready=True,  # Will be ignored in foreground
            no_langfuse=False,
        )

        # Verify up command doesn't have -d flag
        up_call = mock_run_command.call_args_list[1]
        up_cmd = up_call[0][0]
        assert "up" in up_cmd
        assert "-d" not in up_cmd

    @patch("agentsystems_sdk.commands.restart.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_detached_no_wait(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        tmp_path,
    ):
        """Test restart command in detached mode without wait."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,
            wait_ready=False,  # No wait
            no_langfuse=False,
        )

        # Verify gateway wait was NOT called
        mock_wait_gateway.assert_not_called()

    @patch("agentsystems_sdk.commands.restart.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_foreground_with_wait(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        tmp_path,
    ):
        """Test restart command in foreground mode ignores wait flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=False,  # Foreground
            wait_ready=True,  # Should be ignored
            no_langfuse=False,
        )

        # Verify gateway wait was NOT called (foreground mode)
        mock_wait_gateway.assert_not_called()

    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_no_langfuse(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test restart command with --no-langfuse option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,
            wait_ready=False,
            no_langfuse=True,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_down_failure(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test restart command when down command fails."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Make down command fail
        import typer

        mock_run_command.side_effect = typer.Exit(code=1)

        # Execute and expect exception
        try:
            restart_command(
                project_dir=tmp_path,
                detach=True,
                wait_ready=True,
                no_langfuse=False,
            )
        except typer.Exit as e:
            assert e.exit_code == 1

        # Verify only one command was attempted (failed on down)
        assert mock_run_command.call_count == 1

    @patch("agentsystems_sdk.commands.restart.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_up_failure(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        tmp_path,
    ):
        """Test restart command when up command fails."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Make up command fail
        import typer

        def run_command_side_effect(cmd, env):
            if "up" in cmd:
                raise typer.Exit(code=1)

        mock_run_command.side_effect = run_command_side_effect

        # Execute and expect exception
        try:
            restart_command(
                project_dir=tmp_path,
                detach=True,
                wait_ready=True,
                no_langfuse=False,
            )
        except typer.Exit as e:
            assert e.exit_code == 1

        # Verify two commands were attempted
        assert mock_run_command.call_count == 2

        # Verify gateway wait was NOT called (failed before that)
        mock_wait_gateway.assert_not_called()

    @patch("agentsystems_sdk.commands.restart.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.restart.console.print")
    def test_restart_command_gateway_wait_timeout(
        self,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        tmp_path,
    ):
        """Test restart command continues when gateway wait times out."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Gateway wait returns False (timeout)
        mock_wait_gateway.return_value = False

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,
            wait_ready=True,
            no_langfuse=False,
        )

        # Verify gateway wait was called
        mock_wait_gateway.assert_called_once_with()

        # Verify restart still completes
        print_calls = [str(call) for call in mock_console_print.call_args_list]
        assert any("Restart complete" in call for call in print_calls)

    @patch("agentsystems_sdk.commands.restart.run_command_with_env")
    @patch("agentsystems_sdk.commands.restart.compose_args")
    @patch("agentsystems_sdk.commands.restart.ensure_docker_installed")
    def test_restart_command_compose_args_integration(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test restart command properly builds commands with compose args."""
        # Setup with complex compose args
        compose_file = tmp_path / "docker-compose.yml"
        compose_args_list = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-f",
            str(tmp_path / "docker-compose.override.yml"),
            "-p",
            "myproject",
        ]
        mock_compose_args.return_value = (compose_file, compose_args_list)

        # Execute
        restart_command(
            project_dir=tmp_path,
            detach=True,
            wait_ready=False,
            no_langfuse=False,
        )

        # Verify commands include all compose args
        down_cmd = mock_run_command.call_args_list[0][0][0]
        expected_down = compose_args_list + ["down"]
        assert down_cmd == expected_down

        up_cmd = mock_run_command.call_args_list[1][0][0]
        expected_up = compose_args_list + ["up", "-d"]
        assert up_cmd == expected_up
