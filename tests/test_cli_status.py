"""Tests for the status command."""

from unittest.mock import patch

from agentsystems_sdk.commands.status import status_command


class TestStatusCommand:
    """Tests for the status command."""

    @patch("agentsystems_sdk.commands.status.run_command_with_env")
    @patch("agentsystems_sdk.commands.status.compose_args")
    @patch("agentsystems_sdk.commands.status.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.status.os.environ.copy")
    def test_status_command_basic(
        self,
        mock_environ_copy,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test basic status command."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        test_env = {"TEST_VAR": "test_value"}
        mock_environ_copy.return_value = test_env

        # Execute
        status_command(
            project_dir=tmp_path,
            no_langfuse=False,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=True)

        # Verify the command was run
        mock_run_command.assert_called_once()
        cmd = mock_run_command.call_args[0][0]
        assert "ps" in cmd
        assert cmd[-1] == "ps"

        # Verify environment was passed
        assert mock_run_command.call_args[0][1] == test_env

    @patch("agentsystems_sdk.commands.status.run_command_with_env")
    @patch("agentsystems_sdk.commands.status.compose_args")
    @patch("agentsystems_sdk.commands.status.ensure_docker_installed")
    def test_status_command_no_langfuse(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test status command with --no-langfuse option."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        # Execute
        status_command(
            project_dir=tmp_path,
            no_langfuse=True,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.status.run_command_with_env")
    @patch("agentsystems_sdk.commands.status.compose_args")
    @patch("agentsystems_sdk.commands.status.ensure_docker_installed")
    def test_status_command_compose_args_integration(
        self,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        tmp_path,
    ):
        """Test status command properly integrates compose args."""
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
        status_command(
            project_dir=tmp_path,
            no_langfuse=False,
        )

        # Verify full command structure
        cmd = mock_run_command.call_args[0][0]
        expected_cmd = compose_args_list + ["ps"]
        assert cmd == expected_cmd
