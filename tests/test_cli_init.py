"""Tests for the init command."""

from unittest.mock import patch

import pytest
import typer

from agentsystems_sdk.commands.init import init_command


class TestInitCommand:
    """Tests for the init command."""

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.docker_login_if_needed")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copy")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_interactive_mode(
        self,
        mock_stdin,
        mock_prompt,
        mock_run_command,
        mock_shutil_copy,
        mock_set_key,
        mock_ensure_docker,
        mock_docker_login,
        mock_get_images,
        tmp_path,
    ):
        """Test init command in interactive mode with prompts."""
        # Setup
        mock_stdin.isatty.return_value = True  # Interactive mode

        # Mock user inputs via prompt
        mock_prompt.side_effect = [
            "test-project",  # Directory prompt
            "TestOrg",  # Organization name
            "admin@test.com",  # Email
            "password123",  # Password
            "gh-token-123",  # GitHub token
            "docker-token-123",  # Docker token
        ]

        # Mock required images
        mock_get_images.return_value = [
            "agentsystems/gateway:latest",
            "langfuse/langfuse:latest",
        ]

        # Execute
        init_command(
            project_dir=None,  # Will prompt for directory
            branch="main",
            gh_token=None,
            docker_token=None,
        )

        # Verify git clone was called
        assert mock_run_command.call_count >= 1
        clone_call = mock_run_command.call_args_list[0]
        assert clone_call[0][0][0] == "git"
        assert clone_call[0][0][1] == "clone"
        assert "gh-token-123" in clone_call[0][0][4]  # Token in URL

        # Verify Docker was checked
        mock_ensure_docker.assert_called_once()

        # Verify Docker login
        mock_docker_login.assert_called_once_with("docker-token-123")

        # Verify images were pulled
        assert any(
            "docker" in str(call) and "pull" in str(call)
            for call in mock_run_command.call_args_list
        )

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.docker_login_if_needed")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.shutil.copy")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_non_interactive_mode(
        self,
        mock_stdin,
        mock_run_command,
        mock_shutil_copy,
        mock_set_key,
        mock_ensure_docker,
        mock_docker_login,
        mock_get_images,
        tmp_path,
    ):
        """Test init command in non-interactive mode."""
        # Setup
        mock_stdin.isatty.return_value = False  # Non-interactive mode
        project_dir = tmp_path / "test-project"

        # Mock required images
        mock_get_images.return_value = ["agentsystems/gateway:latest"]

        # Execute
        init_command(
            project_dir=project_dir,
            branch="main",
            gh_token="gh-token-123",
            docker_token="docker-token-123",
        )

        # Verify git clone was called
        assert mock_run_command.call_count >= 1
        clone_call = mock_run_command.call_args_list[0]
        assert clone_call[0][0][0] == "git"
        assert clone_call[0][0][1] == "clone"

        # Verify default Langfuse values were used
        langfuse_calls = [
            call for call in mock_set_key.call_args_list if "LANGFUSE" in call[0][1]
        ]
        assert len(langfuse_calls) > 0

        # Find the org ID call
        org_id_call = next(
            (
                call
                for call in mock_set_key.call_args_list
                if call[0][1] == "LANGFUSE_INIT_ORG_ID"
            ),
            None,
        )
        assert org_id_call is not None
        assert org_id_call[0][2] == '"org"'  # Default org ID

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

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_env_file_creation(
        self,
        mock_stdin,
        mock_run_command,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command creates .env file from .env.example."""
        # Setup
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"

        # Mock that git clone creates the directory with .env.example
        def create_project_structure(cmd):
            if "clone" in cmd:
                project_dir.mkdir(parents=True)
                (project_dir / ".env.example").write_text("# Example env file")

        mock_run_command.side_effect = create_project_structure
        mock_get_images.return_value = []

        # Execute
        init_command(
            project_dir=project_dir,
            branch="main",
            gh_token=None,
            docker_token=None,
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
    @patch("agentsystems_sdk.commands.init.docker_login_if_needed")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_docker_pull_failure_retry(
        self,
        mock_stdin,
        mock_prompt,
        mock_run_command,
        mock_set_key,
        mock_ensure_docker,
        mock_docker_login,
        mock_get_images,
        tmp_path,
    ):
        """Test init command retries docker pull with token on failure."""
        # Setup
        mock_stdin.isatty.return_value = True
        project_dir = tmp_path / "test-project"

        # Mock user inputs
        mock_prompt.side_effect = [
            "TestOrg",  # Organization name
            "admin@test.com",  # Email
            "password123",  # Password
            "",  # No GitHub token
            "docker-token-retry",  # Docker token prompt after pull failure
        ]

        # Mock required images
        mock_get_images.return_value = ["private/image:latest"]

        # Mock run_command to fail on first docker pull, succeed on retry
        pull_attempts = 0

        def mock_run_side_effect(cmd):
            nonlocal pull_attempts
            if "clone" in cmd:
                project_dir.mkdir(parents=True)
                (project_dir / ".env.example").write_text("")
            elif "docker" in cmd and "pull" in cmd:
                pull_attempts += 1
                if pull_attempts == 1:
                    raise typer.Exit(code=1)
                # Success on second attempt

        mock_run_command.side_effect = mock_run_side_effect

        # Execute
        init_command(
            project_dir=project_dir,
            branch="main",
            gh_token="gh-token",
            docker_token=None,  # No initial docker token
        )

        # Verify docker login was called after failure
        mock_docker_login.assert_called_with("docker-token-retry")

        # Verify pull was attempted twice
        assert pull_attempts == 2

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_no_images_to_pull(
        self,
        mock_stdin,
        mock_run_command,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command handles case with no images to pull."""
        # Setup
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"

        # No images to pull
        mock_get_images.return_value = []

        # Mock git clone to create directory
        def create_project_structure(cmd):
            if "clone" in cmd:
                project_dir.mkdir(parents=True)
                (project_dir / ".env.example").write_text("")

        mock_run_command.side_effect = create_project_structure

        # Execute
        init_command(
            project_dir=project_dir,
            branch="main",
            gh_token=None,
            docker_token=None,
        )

        # Verify no docker pull commands were issued
        docker_pull_calls = [
            call for call in mock_run_command.call_args_list if "pull" in str(call)
        ]
        assert len(docker_pull_calls) == 0

    @patch("agentsystems_sdk.commands.init.get_required_images")
    @patch("agentsystems_sdk.commands.init.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.init.set_key")
    @patch("agentsystems_sdk.commands.init.run_command")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_custom_branch(
        self,
        mock_stdin,
        mock_run_command,
        mock_set_key,
        mock_ensure_docker,
        mock_get_images,
        tmp_path,
    ):
        """Test init command with custom branch."""
        # Setup
        mock_stdin.isatty.return_value = False
        project_dir = tmp_path / "test-project"
        custom_branch = "develop"

        mock_get_images.return_value = []

        # Mock git clone
        def create_project_structure(cmd):
            if "clone" in cmd:
                project_dir.mkdir(parents=True)
                (project_dir / ".env.example").write_text("")

        mock_run_command.side_effect = create_project_structure

        # Execute
        init_command(
            project_dir=project_dir,
            branch=custom_branch,
            gh_token=None,
            docker_token=None,
        )

        # Verify git clone used custom branch
        clone_call = mock_run_command.call_args_list[0]
        assert "--branch" in clone_call[0][0]
        assert custom_branch in clone_call[0][0]

    @patch("agentsystems_sdk.commands.init.re.match")
    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_email_validation(
        self,
        mock_stdin,
        mock_prompt,
        mock_re_match,
        tmp_path,
    ):
        """Test init command validates email in interactive mode."""
        # Setup
        mock_stdin.isatty.return_value = True

        # Mock email validation to fail first, then pass
        mock_re_match.side_effect = [
            None,
            True,
            True,
        ]  # First email invalid, second valid

        # Mock user inputs
        mock_prompt.side_effect = [
            str(tmp_path / "test-project"),  # Directory
            "TestOrg",  # Organization name
            "invalid-email",  # Invalid email
            "valid@email.com",  # Valid email
            "password123",  # Password
            "",  # No GitHub token
            "",  # No Docker token
        ]

        with patch("agentsystems_sdk.commands.init.run_command"):
            with patch("agentsystems_sdk.commands.init.set_key"):
                with patch("agentsystems_sdk.commands.init.ensure_docker_installed"):
                    with patch(
                        "agentsystems_sdk.commands.init.get_required_images",
                        return_value=[],
                    ):
                        # Execute
                        init_command(
                            project_dir=None,
                            branch="main",
                            gh_token=None,
                            docker_token=None,
                        )

        # Verify email was prompted twice
        email_prompts = [
            call for call in mock_prompt.call_args_list if "email" in str(call)
        ]
        assert len(email_prompts) == 2

    @patch("agentsystems_sdk.commands.init.typer.prompt")
    @patch("agentsystems_sdk.commands.init.sys.stdin")
    def test_init_command_password_validation(
        self,
        mock_stdin,
        mock_prompt,
        tmp_path,
    ):
        """Test init command validates password length in interactive mode."""
        # Setup
        mock_stdin.isatty.return_value = True

        # Mock user inputs
        mock_prompt.side_effect = [
            str(tmp_path / "test-project"),  # Directory
            "TestOrg",  # Organization name
            "admin@test.com",  # Email
            "short",  # Too short password
            "password123",  # Valid password
            "",  # No GitHub token
            "",  # No Docker token
        ]

        with patch("agentsystems_sdk.commands.init.run_command"):
            with patch("agentsystems_sdk.commands.init.set_key"):
                with patch("agentsystems_sdk.commands.init.ensure_docker_installed"):
                    with patch(
                        "agentsystems_sdk.commands.init.get_required_images",
                        return_value=[],
                    ):
                        # Execute
                        init_command(
                            project_dir=None,
                            branch="main",
                            gh_token=None,
                            docker_token=None,
                        )

        # Verify password was prompted twice
        password_prompts = [
            call
            for call in mock_prompt.call_args_list
            if "password" in str(call) and "hide_input" in str(call)
        ]
        assert len(password_prompts) == 2
