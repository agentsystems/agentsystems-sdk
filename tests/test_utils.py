"""Tests for the utils module."""

import subprocess
from unittest.mock import Mock, patch, MagicMock

import docker
import pytest
import typer

from agentsystems_sdk.utils import (
    run_command,
    run_command_with_env,
    ensure_docker_installed,
    docker_login_if_needed,
    ensure_agents_net,
    compose_args,
    wait_for_gateway_ready,
    read_env_file,
    get_required_images,
    cleanup_langfuse_init_vars,
)


class TestUtils:
    """Tests for utility functions."""

    def test_run_command_success(self):
        """Test run_command with successful execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            run_command(["echo", "test"])

            mock_run.assert_called_once_with(["echo", "test"], check=True)

    def test_run_command_failure(self):
        """Test run_command with failed execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["false"])

            with pytest.raises(typer.Exit) as exc_info:
                run_command(["false"])

            assert exc_info.value.exit_code == 1

    def test_run_command_with_env_success(self):
        """Test run_command_with_env with successful execution."""
        with patch("subprocess.check_call") as mock_check_call:
            env = {"TEST": "value"}

            run_command_with_env(["echo", "test"], env)

            mock_check_call.assert_called_once_with(["echo", "test"], env=env)

    def test_run_command_with_env_failure(self):
        """Test run_command_with_env with failed execution."""
        with patch("subprocess.check_call") as mock_check_call:
            mock_check_call.side_effect = subprocess.CalledProcessError(2, ["false"])

            with pytest.raises(typer.Exit) as exc_info:
                run_command_with_env(["false"], {})

            assert exc_info.value.exit_code == 2

    @patch("shutil.which")
    def test_ensure_docker_installed_success(self, mock_which):
        """Test ensure_docker_installed when Docker is present."""
        mock_which.return_value = "/usr/bin/docker"

        # Should not raise
        ensure_docker_installed()

        mock_which.assert_called_once_with("docker")

    @patch("shutil.which")
    def test_ensure_docker_installed_failure(self, mock_which):
        """Test ensure_docker_installed when Docker is missing."""
        mock_which.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            ensure_docker_installed()

        assert exc_info.value.exit_code == 1

    def test_docker_login_if_needed_no_token(self):
        """Test docker_login_if_needed with no token."""
        # Should return early without doing anything
        docker_login_if_needed(None)

    @patch("subprocess.Popen")
    def test_docker_login_if_needed_success(self, mock_popen):
        """Test docker_login_if_needed with successful login."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        docker_login_if_needed("test-token")

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args == [
            "docker",
            "login",
            "--username",
            "agentsystems",
            "--password-stdin",
        ]

    @patch("subprocess.Popen")
    def test_docker_login_if_needed_failure(self, mock_popen):
        """Test docker_login_if_needed with failed login."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = ("", "Login failed")
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        with pytest.raises(typer.Exit) as exc_info:
            docker_login_if_needed("bad-token")

        assert exc_info.value.exit_code == 1

    @patch("subprocess.Popen")
    def test_docker_login_if_needed_exception(self, mock_popen):
        """Test docker_login_if_needed with exception."""
        mock_popen.side_effect = Exception("Connection error")

        with pytest.raises(typer.Exit) as exc_info:
            docker_login_if_needed("test-token")

        assert exc_info.value.exit_code == 1

    @patch("docker.from_env")
    def test_ensure_agents_net_already_exists(self, mock_docker_from_env):
        """Test ensure_agents_net when network already exists."""
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        # Network exists
        mock_client.networks.get.return_value = Mock()

        ensure_agents_net()

        mock_client.networks.get.assert_called_once_with("agents_net")
        mock_client.networks.create.assert_not_called()

    @patch("docker.from_env")
    def test_ensure_agents_net_create(self, mock_docker_from_env):
        """Test ensure_agents_net creates network when missing."""
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        # Network doesn't exist
        mock_client.networks.get.side_effect = docker.errors.NotFound("Not found")

        ensure_agents_net()

        mock_client.networks.create.assert_called_once_with(
            "agents_net",
            driver="bridge",
            options={"com.docker.network.bridge.host_binding_ipv4": "127.0.0.1"},
        )

    @patch("docker.from_env")
    def test_ensure_agents_net_create_failure(self, mock_docker_from_env):
        """Test ensure_agents_net handles creation failure."""
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        # Network doesn't exist
        mock_client.networks.get.side_effect = docker.errors.NotFound("Not found")
        # Creation fails
        mock_client.networks.create.side_effect = docker.errors.APIError("API error")

        with pytest.raises(typer.Exit) as exc_info:
            ensure_agents_net()

        assert exc_info.value.exit_code == 1

    def test_compose_args_basic(self, tmp_path):
        """Test compose_args with basic setup."""
        # Create compose file
        compose_dir = tmp_path / "compose" / "local"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        with patch("agentsystems_sdk.utils.COMPOSE_BIN", ["docker", "compose"]):
            core_file, args = compose_args(tmp_path)

        assert core_file == compose_file
        assert args == [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-p",
            "agentsystems",
        ]

    def test_compose_args_with_langfuse(self, tmp_path):
        """Test compose_args with Langfuse file."""
        # Create compose files
        compose_dir = tmp_path / "compose" / "local"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        langfuse_dir = tmp_path / "langfuse"
        langfuse_dir.mkdir()
        langfuse_file = langfuse_dir / "docker-compose.langfuse.yml"
        langfuse_file.write_text("version: '3'")

        with patch("agentsystems_sdk.utils.COMPOSE_BIN", ["docker-compose"]):
            core_file, args = compose_args(tmp_path, langfuse=True)

        assert args == [
            "docker-compose",
            "-f",
            str(compose_file),
            "-f",
            str(langfuse_file),
            "-p",
            "agentsystems",
        ]

    def test_compose_args_no_compose_bin(self, tmp_path):
        """Test compose_args when docker-compose is not found."""
        with patch("agentsystems_sdk.utils.COMPOSE_BIN", []):
            with pytest.raises(typer.Exit) as exc_info:
                compose_args(tmp_path)

            assert exc_info.value.exit_code == 1

    def test_compose_args_missing_compose_file(self, tmp_path):
        """Test compose_args when compose file is missing."""
        with patch("agentsystems_sdk.utils.COMPOSE_BIN", ["docker", "compose"]):
            with pytest.raises(typer.Exit) as exc_info:
                compose_args(tmp_path)

            assert exc_info.value.exit_code == 1

    @patch("requests.get")
    @patch("time.time")
    def test_wait_for_gateway_ready_success(self, mock_time, mock_get):
        """Test wait_for_gateway_ready when gateway becomes ready."""
        # Mock time to avoid actual waiting
        mock_time.side_effect = [0, 0.5, 1]  # Start, first check, success

        # First call fails, second succeeds
        mock_get.side_effect = [
            Mock(status_code=503),
            Mock(status_code=200),
        ]

        result = wait_for_gateway_ready(timeout=30, interval=0.1)

        assert result is True
        assert mock_get.call_count == 2

    @patch("requests.get")
    @patch("time.time")
    def test_wait_for_gateway_ready_timeout(self, mock_time, mock_get):
        """Test wait_for_gateway_ready timeout."""
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 31]  # Start, past deadline

        mock_get.return_value = Mock(status_code=503)

        result = wait_for_gateway_ready(timeout=30, interval=0.1)

        assert result is False

    @patch("requests.get")
    @patch("time.time")
    def test_wait_for_gateway_ready_exception(self, mock_time, mock_get):
        """Test wait_for_gateway_ready handles request exceptions."""
        # Mock time
        mock_time.side_effect = [0, 0.5, 1, 2]

        # First call raises exception, second succeeds
        import requests

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            Mock(status_code=200),
        ]

        result = wait_for_gateway_ready(timeout=30, interval=0.1)

        assert result is True

    def test_read_env_file(self, tmp_path):
        """Test read_env_file with various formats."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            """
# Comment line
SIMPLE_VAR=value1
QUOTED_VAR="value with spaces"
SINGLE_QUOTED='single quotes'
EMPTY_VAR=
EQUALS_IN_VALUE=key=value
# COMMENTED_VAR=should_not_be_included
        """
        )

        result = read_env_file(env_file)

        assert result == {
            "SIMPLE_VAR": "value1",
            "QUOTED_VAR": "value with spaces",
            "SINGLE_QUOTED": "single quotes",
            "EMPTY_VAR": "",
            "EQUALS_IN_VALUE": "key=value",
        }

    def test_get_required_images(self):
        """Test get_required_images returns expected list."""
        images = get_required_images()

        assert isinstance(images, list)
        # Images are now pulled during 'agentsystems up', not 'agentsystems init'
        assert len(images) == 0

    def test_cleanup_langfuse_init_vars_first_time(self, tmp_path):
        """Test cleanup_langfuse_init_vars on first cleanup."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            """
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_INIT_ORG_ID=org
LANGFUSE_INIT_ORG_NAME=MyOrg
LANGFUSE_INIT_USER_EMAIL=admin@example.com
OTHER_VAR=value
        """
        )

        cleanup_langfuse_init_vars(env_file)

        content = env_file.read_text()

        # Check that init vars are commented out
        assert "# LANGFUSE_INIT_ORG_ID=org" in content
        assert "# LANGFUSE_INIT_ORG_NAME=MyOrg" in content
        assert "# LANGFUSE_INIT_USER_EMAIL=admin@example.com" in content

        # Check that other vars are untouched
        assert "LANGFUSE_HOST=http://langfuse-web:3000" in content
        assert "OTHER_VAR=value" in content

        # Check that notice was added
        assert "# --- Langfuse initialization values" in content

    def test_cleanup_langfuse_init_vars_already_cleaned(self, tmp_path):
        """Test cleanup_langfuse_init_vars when already cleaned."""
        env_file = tmp_path / ".env"
        original_content = """
LANGFUSE_HOST=http://langfuse-web:3000
OTHER_VAR=value

# --- Langfuse initialization values (no longer used after first start) ---
# You can remove these lines or keep them for reference.
# LANGFUSE_INIT_ORG_ID=org
        """
        env_file.write_text(original_content)

        cleanup_langfuse_init_vars(env_file)

        # Content should be unchanged
        assert env_file.read_text() == original_content

    def test_cleanup_langfuse_init_vars_no_init_vars(self, tmp_path):
        """Test cleanup_langfuse_init_vars when no init vars present."""
        env_file = tmp_path / ".env"
        original_content = """
LANGFUSE_HOST=http://langfuse-web:3000
OTHER_VAR=value
        """
        env_file.write_text(original_content)

        cleanup_langfuse_init_vars(env_file)

        # Should add notice but no commented vars
        content = env_file.read_text()
        assert "OTHER_VAR=value" in content
        assert "# ---" not in content  # No notice added when no init vars
