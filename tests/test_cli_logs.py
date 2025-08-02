"""Tests for the logs command."""

from unittest.mock import patch

from agentsystems_sdk.commands.logs import logs_command


class TestLogsCommand:
    """Tests for the logs command."""

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.logs.os.environ.copy")
    def test_logs_command_basic(
        self,
        mock_environ_copy,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test basic logs command with default options (follow=True)."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        test_env = {"TEST_VAR": "test_value"}
        mock_environ_copy.return_value = test_env

        # Execute
        logs_command(
            project_dir=tmp_path,
            follow=True,  # Default
            no_langfuse=False,
            services=None,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=True)

        # Verify the command was run with -f flag
        mock_run_command.assert_called_once()
        cmd = mock_run_command.call_args[0][0]
        assert "logs" in cmd
        assert "-f" in cmd  # Follow flag
        assert cmd[-1] == "-f"  # No services specified

        # Verify environment was passed
        assert mock_run_command.call_args[0][1] == test_env

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_no_follow(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command with --no-follow option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        logs_command(
            project_dir=tmp_path,
            follow=False,
            no_langfuse=False,
            services=None,
        )

        # Verify the command was run without -f flag
        cmd = mock_run_command.call_args[0][0]
        assert "logs" in cmd
        # Check that -f doesn't appear after "logs" (compose -f is before logs)
        logs_index = cmd.index("logs")
        assert "-f" not in cmd[logs_index:]

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_with_services(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command with specific services."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute with specific services
        services = ["gateway", "database"]
        logs_command(
            project_dir=tmp_path,
            follow=True,
            no_langfuse=False,
            services=services,
        )

        # Verify services were added to command
        cmd = mock_run_command.call_args[0][0]
        assert "logs" in cmd
        assert "-f" in cmd
        assert "gateway" in cmd
        assert "database" in cmd
        # Verify order: logs -f gateway database
        logs_index = cmd.index("logs")
        assert cmd[logs_index + 1] == "-f"
        assert cmd[logs_index + 2] == "gateway"
        assert cmd[logs_index + 3] == "database"

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_no_langfuse(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command with --no-langfuse option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        logs_command(
            project_dir=tmp_path,
            follow=True,
            no_langfuse=True,
            services=None,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_single_service_no_follow(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command with single service and no follow."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        logs_command(
            project_dir=tmp_path,
            follow=False,
            no_langfuse=False,
            services=["agent-control-plane"],
        )

        # Verify command structure
        cmd = mock_run_command.call_args[0][0]
        assert "logs" in cmd
        # Check that -f doesn't appear after "logs" (compose -f is before logs)
        logs_index = cmd.index("logs")
        assert "-f" not in cmd[logs_index:]  # No follow
        assert "agent-control-plane" in cmd

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_empty_services_list(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command with empty services list."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute with empty list
        logs_command(
            project_dir=tmp_path,
            follow=True,
            no_langfuse=False,
            services=[],  # Empty list
        )

        # Verify command doesn't include any services
        cmd = mock_run_command.call_args[0][0]
        assert "logs" in cmd
        # Find -f after logs (not the compose -f)
        logs_index = cmd.index("logs")
        assert "-f" in cmd[logs_index:]
        # The command should end with "logs -f" (no services)
        assert cmd[-1] == "-f" or (cmd[-2] == "logs" and cmd[-1] == "-f")

    @patch("agentsystems_sdk.commands.logs.run_command_with_env")
    @patch("agentsystems_sdk.commands.logs.compose_args")
    @patch("agentsystems_sdk.commands.logs.ensure_docker_installed")
    def test_logs_command_compose_args_integration(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test logs command properly integrates compose args."""
        # Setup with more complex compose args
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
        logs_command(
            project_dir=tmp_path,
            follow=True,
            no_langfuse=False,
            services=["web"],
        )

        # Verify full command structure
        cmd = mock_run_command.call_args[0][0]
        expected_cmd = compose_args_list + ["logs", "-f", "web"]
        assert cmd == expected_cmd
