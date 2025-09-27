"""Tests for the init command with local scaffold."""

from unittest.mock import patch, MagicMock

import pytest
import typer

from agentsystems_sdk.commands.init import init_command


class TestInitCommand:
    """Tests for the init command with local scaffold."""

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copy")
    @patch("agentsystems_sdk.commands.init.shutil.copytree")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_interactive_mode(
        self,
        mock_stdin,
        mock_prompt,
        mock_run_command,
        mock_copytree,
        mock_shutil_copy,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command in interactive mode with prompts."""
        # Setup
        mock_stdin.isatty.return_value = True  # Interactive mode

        # Mock user inputs via prompt - only directory prompt now
        mock_prompt.return_value = "test-project"

        # Mock required images
        mock_get_images.return_value = [
            "ghcr.io/agentsystems/agent-control-plane:latest",
            "langfuse/langfuse:latest",
        ]

        # Execute
        init_command(
            project_dir=None,  # Will prompt for directory
        )

        # Verify scaffold was copied
        mock_copytree.assert_called_once()
        assert "deployments_scaffold" in str(mock_copytree.call_args[0][0])

        # Verify Docker was checked
        mock_ensure_docker.assert_called_once()

        # Verify images were pulled (no Docker login needed for public images)
        assert any(
            "docker" in str(call) and "pull" in str(call)
            for call in mock_run_command.call_args_list
        )

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copy")
    @patch("agentsystems_sdk.commands.init.shutil.copytree")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_non_interactive_mode(
        self,
        mock_stdin,
        mock_run_command,
        mock_copytree,
        mock_shutil_copy,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command in non-interactive mode."""
        # Setup
        mock_stdin.isatty.return_value = False  # Non-interactive mode
        project_dir = tmp_path / "test-project"

        # Mock required images
        mock_get_images.return_value = [
            "ghcr.io/agentsystems/agent-control-plane:latest"
        ]

        # Execute
        init_command(
            project_dir=project_dir,
        )

        # Verify scaffold was copied
        mock_copytree.assert_called_once()
        assert "deployments_scaffold" in str(mock_copytree.call_args[0][0])
        assert str(project_dir) in str(mock_copytree.call_args[0][1])

    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_missing_project_dir_non_interactive(self, mock_stdin):
        """Test init command fails when project_dir missing in non-interactive mode."""
        mock_stdin.isatty.return_value = False

        with pytest.raises(typer.Exit) as exc_info:
            init_command(project_dir=None)

        assert exc_info.value.exit_code == 1

    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_non_empty_directory(self, mock_stdin, tmp_path):
        """Test init command fails when target directory is not empty."""
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "existing-project"
        project_dir.mkdir()
        (project_dir / "existing-file.txt").write_text("content")

        with pytest.raises(typer.Exit) as exc_info:
            init_command(project_dir=project_dir)

        assert exc_info.value.exit_code == 1

    @patch("agentsystems_sdk.commands.init.pathlib.Path")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_scaffold_not_found(self, mock_stdin, mock_path, tmp_path):
        """Test init command fails when scaffold directory is not found."""
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"

        # Mock scaffold directory not existing
        mock_scaffold = MagicMock()
        mock_scaffold.exists.return_value = False
        mock_path.return_value.__truediv__.return_value = mock_scaffold

        with pytest.raises(typer.Exit) as exc_info:
            init_command(project_dir=project_dir)

        assert exc_info.value.exit_code == 1

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copytree")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_env_file_creation(
        self,
        mock_stdin,
        mock_run_command,
        mock_copytree,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command creates .env file from .env.example."""
        # Setup
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"

        # Mock copytree to create directory with .env.example
        def create_project_structure(src, dst):
            dst.mkdir(parents=True)
            (dst / ".env.example").write_text("# Example env file")

        mock_copytree.side_effect = create_project_structure
        mock_get_images.return_value = []

        # Execute
        init_command(
            project_dir=project_dir,
        )

        # Verify set_key was called to populate the .env file
        assert mock_set_key.call_count > 0

        # Check that Langfuse variables were set
        langfuse_vars = [
            "LANGFUSE_INIT_ORG_ID",
            "LANGFUSE_INIT_ORG_NAME",
            "LANGFUSE_INIT_PROJECT_ID",
            "LANGFUSE_INIT_PROJECT_NAME",
            "LANGFUSE_INIT_USER_NAME",
            "LANGFUSE_INIT_USER_EMAIL",
            "LANGFUSE_INIT_USER_PASSWORD",
            "LANGFUSE_INIT_PROJECT_PUBLIC_KEY",
            "LANGFUSE_INIT_PROJECT_SECRET_KEY",
            "LANGFUSE_HOST",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
        ]

        set_keys = [call[0][1] for call in mock_set_key.call_args_list]
        for var in langfuse_vars:
            assert var in set_keys

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copytree")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_no_images_to_pull(
        self,
        mock_stdin,
        mock_run_command,
        mock_copytree,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command handles case with no images to pull."""
        # Setup
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"

        # Mock copytree to create directory
        def create_project_structure(src, dst):
            dst.mkdir(parents=True)

        mock_copytree.side_effect = create_project_structure
        mock_get_images.return_value = []  # No images

        # Execute
        init_command(
            project_dir=project_dir,
        )

        # Verify no docker pull commands were executed
        assert not any(
            "docker" in str(call) and "pull" in str(call)
            for call in mock_run_command.call_args_list
        )

    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_auto_generates_credentials(
        self,
        mock_stdin,
        mock_prompt,
        tmp_path,
    ):
        """Test init command auto-generates email and password."""
        # Setup
        mock_stdin.isatty.return_value = True

        # Mock user input - only directory prompt now
        mock_prompt.return_value = str(tmp_path / "test-project")

        # Mock other dependencies to avoid actual execution
        with patch("agentsystems_sdk.commands.init.shutil.copytree"):
            with patch("agentsystems_sdk.commands.init.ensure_docker_installed"):
                with patch(
                    "agentsystems_sdk.commands.init.get_required_images",
                    return_value=[],
                ):
                    with patch(
                        "agentsystems_sdk.commands.init.set_key"
                    ) as mock_set_key:
                        # Execute
                        init_command(project_dir=None)

                        # Verify auto-generated credentials were set
                        set_key_calls = {
                            call[0][1]: call[0][2]
                            for call in mock_set_key.call_args_list
                        }

                        # Check email is the generic one
                        assert (
                            set_key_calls["LANGFUSE_INIT_USER_EMAIL"]
                            == '"admin@localhost.local"'
                        )

                        # Check password was generated (16 alphanumeric chars)
                        password = set_key_calls["LANGFUSE_INIT_USER_PASSWORD"].strip(
                            '"'
                        )
                        assert len(password) == 16
                        assert password.isalnum()

    @patch("agentsystems_sdk.commands.init.generate_secure_password")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_password_generation(
        self,
        mock_stdin,
        mock_generate_password,
        tmp_path,
    ):
        """Test init command generates secure password automatically."""
        # Setup
        mock_stdin.isatty.return_value = True
        mock_generate_password.return_value = "SecurePass123456"

        # Mock other dependencies to avoid actual execution
        with patch("agentsystems_sdk.commands.init.shutil.copytree"):
            with patch("agentsystems_sdk.commands.init.ensure_docker_installed"):
                with patch(
                    "agentsystems_sdk.commands.init.get_required_images",
                    return_value=[],
                ):
                    with patch(
                        "agentsystems_sdk.commands.init.set_key"
                    ) as mock_set_key:
                        # Execute with explicit project_dir to avoid prompt
                        init_command(project_dir=tmp_path / "test-project")

                        # Verify password was generated
                        mock_generate_password.assert_called_once()

                        # Verify the generated password was set
                        set_key_calls = {
                            call[0][1]: call[0][2]
                            for call in mock_set_key.call_args_list
                        }
                        assert (
                            set_key_calls["LANGFUSE_INIT_USER_PASSWORD"]
                            == '"SecurePass123456"'
                        )
