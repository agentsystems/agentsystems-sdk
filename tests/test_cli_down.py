"""Tests for the down command."""

from unittest.mock import Mock, patch, MagicMock


from agentsystems_sdk.commands.down import down_command


class TestDownCommand:
    """Tests for the down command."""

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_basic(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test basic down command without any flags."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=False,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=True)

        # Verify the command was run without -v flag
        mock_run_command.assert_called_once()
        cmd = mock_run_command.call_args[0][0]
        assert "down" in cmd
        assert "-v" not in cmd

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_delete_volumes(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test down command with --delete-volumes flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=True,
            delete_containers=False,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Verify the command was run with -v flag
        mock_run_command.assert_called_once()
        cmd = mock_run_command.call_args[0][0]
        assert "down" in cmd
        assert "-v" in cmd

    @patch("agentsystems_sdk.commands.down.docker.from_env")
    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_delete_containers(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_docker_from_env,
        tmp_path,
    ):
        """Test down command with --delete-containers flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Mock Docker client and containers
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        # Create mock containers
        mock_container1 = Mock()
        mock_container1.name = "agent-1"
        mock_container2 = Mock()
        mock_container2.name = "agent-2"

        mock_client.containers.list.return_value = [mock_container1, mock_container2]

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=True,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Verify
        mock_docker_from_env.assert_called_once()
        mock_client.containers.list.assert_called_once_with(
            all=True, filters={"label": "agent.enabled=true"}
        )

        # Verify containers were removed
        mock_container1.remove.assert_called_once_with(force=True)
        mock_container2.remove.assert_called_once_with(force=True)

    @patch("agentsystems_sdk.commands.down.docker.from_env")
    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_delete_all(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_docker_from_env,
        tmp_path,
    ):
        """Test down command with --delete-all flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Mock Docker client
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client
        mock_client.containers.list.return_value = []

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,  # Will be overridden by delete_all
            delete_containers=False,  # Will be overridden by delete_all
            delete_all=True,
            volumes=None,
            no_langfuse=False,
        )

        # Verify the command was run with -v flag
        cmd = mock_run_command.call_args[0][0]
        assert "down" in cmd
        assert "-v" in cmd

        # Verify Docker client was called for container removal
        mock_docker_from_env.assert_called_once()

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.down.typer.secho")
    def test_down_command_deprecated_volumes_flag(
        self,
        mock_secho,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test down command with deprecated --volumes flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute with deprecated volumes=True
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=False,
            delete_all=False,
            volumes=True,  # Deprecated flag
            no_langfuse=False,
        )

        # Verify deprecation warning was shown
        mock_secho.assert_called_once()
        assert "DEPRECATED" in mock_secho.call_args[0][0]

        # Verify the command was run with -v flag (volumes=True promotes to delete_volumes)
        cmd = mock_run_command.call_args[0][0]
        assert "-v" in cmd

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_no_langfuse(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test down command with --no-langfuse flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=False,
            delete_all=False,
            volumes=None,
            no_langfuse=True,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.down.docker.from_env")
    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.down.console.print")
    def test_down_command_container_removal_failure(
        self,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_docker_from_env,
        tmp_path,
    ):
        """Test down command handles container removal failures gracefully."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Mock Docker client and container that fails to remove
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        mock_container = Mock()
        mock_container.name = "agent-error"
        mock_container.remove.side_effect = Exception("Permission denied")

        mock_client.containers.list.return_value = [mock_container]

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=True,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Verify error was handled gracefully
        mock_container.remove.assert_called_once_with(force=True)

        # Check that error message was printed
        error_prints = [
            call
            for call in mock_console_print.call_args_list
            if "Failed to remove" in str(call)
        ]
        assert len(error_prints) > 0

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.down.typer.secho")
    def test_down_command_deprecated_no_volumes_flag(
        self,
        mock_secho,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test down command with deprecated --no-volumes flag."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute with deprecated volumes=False
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=False,
            delete_all=False,
            volumes=False,  # Deprecated flag
            no_langfuse=False,
        )

        # Verify deprecation warning was shown
        mock_secho.assert_called_once()
        assert "DEPRECATED" in mock_secho.call_args[0][0]

        # Verify the command was run without -v flag
        cmd = mock_run_command.call_args[0][0]
        assert "down" in cmd
        assert "-v" not in cmd

    @patch("agentsystems_sdk.commands.down.docker.from_env")
    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    def test_down_command_no_agent_containers(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_docker_from_env,
        tmp_path,
    ):
        """Test down command with --delete-containers when no agent containers exist."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Mock Docker client with no containers
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client
        mock_client.containers.list.return_value = []

        # Execute
        down_command(
            project_dir=tmp_path,
            delete_volumes=False,
            delete_containers=True,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Verify Docker client was called but no containers were removed
        mock_docker_from_env.assert_called_once()
        mock_client.containers.list.assert_called_once_with(
            all=True, filters={"label": "agent.enabled=true"}
        )

    @patch("agentsystems_sdk.commands.down.run_command_with_env")
    @patch("agentsystems_sdk.commands.down.compose_args")
    @patch("agentsystems_sdk.commands.down.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.down.console.print")
    def test_down_command_final_message(
        self,
        mock_console_print,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test down command displays correct final message based on flags."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute with delete_volumes
        down_command(
            project_dir=tmp_path,
            delete_volumes=True,
            delete_containers=False,
            delete_all=False,
            volumes=None,
            no_langfuse=False,
        )

        # Check final message includes "Volumes deleted"
        final_prints = [
            call
            for call in mock_console_print.call_args_list
            if "Platform stopped" in str(call) and "Volumes deleted" in str(call)
        ]
        assert len(final_prints) > 0
