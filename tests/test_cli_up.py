"""Tests for the up command."""

from unittest.mock import Mock, patch, MagicMock

import pytest
import typer

from agentsystems_sdk.commands.up import (
    AgentStartMode,
    up_command,
)


class TestUpCommand:
    """Tests for the up command - focusing on logic, not Docker operations."""

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.setup_agents_from_config")
    @patch("agentsystems_sdk.commands.up.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.cleanup_langfuse_init_vars")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    @patch("agentsystems_sdk.commands.up.Config")
    def test_up_command_detached_with_wait(
        self,
        mock_config,
        mock_tempdir,
        mock_cleanup_vars,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        mock_setup_agents,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command in detached mode with wait."""
        # Setup
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        mock_wait_gateway.return_value = True

        # Mock temporary directory for Docker config
        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        # Mock subprocess for docker login
        mock_subprocess.return_value = Mock(returncode=0)

        # Mock Config class
        mock_cfg_instance = Mock()
        mock_cfg_instance.agents = [Mock(name="test-agent")]
        mock_cfg_instance.registries = {}
        mock_config.return_value = mock_cfg_instance

        # Create required files
        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=value")

        # Execute
        up_command(
            project_dir=tmp_path,
            detach=True,
            fresh=False,
            wait_ready=True,
            agents_mode=AgentStartMode.all,
            no_langfuse=False,
            env_file=None,
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

        # Verify
        mock_ensure_docker.assert_called_once()
        assert mock_run_command.call_count >= 1  # At least one compose command
        mock_wait_gateway.assert_called_once()
        mock_setup_agents.assert_called_once()
        mock_cleanup_vars.assert_called_once_with(env_file)

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.setup_agents_from_config")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    @patch("agentsystems_sdk.commands.up.Config")
    def test_up_command_foreground_mode(
        self,
        mock_config,
        mock_tempdir,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_setup_agents,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command in foreground mode (no detach)."""
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        mock_subprocess.return_value = Mock(returncode=0)

        # Mock Config class
        mock_cfg_instance = Mock()
        mock_cfg_instance.agents = [Mock(name="test-agent")]
        mock_cfg_instance.registries = {}
        mock_config.return_value = mock_cfg_instance

        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )
        env_file = tmp_path / ".env"
        env_file.write_text("")

        up_command(
            project_dir=tmp_path,
            detach=False,  # Foreground mode
            fresh=False,
            wait_ready=False,  # Wait not applicable in foreground
            agents_mode=AgentStartMode.none,
            no_langfuse=False,
            env_file=None,
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

        # Should call setup_agents with none mode
        mock_setup_agents.assert_called_once_with(
            mock_cfg_instance, tmp_path, AgentStartMode.none
        )

    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    def test_up_command_missing_env_file(self, mock_ensure_docker, tmp_path):
        """Test up command fails when .env file is missing."""
        # Create config but not .env
        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )

        with pytest.raises(typer.Exit):
            up_command(
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

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.setup_agents_from_config")
    @patch("agentsystems_sdk.commands.up.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    @patch("agentsystems_sdk.commands.up.Config")
    def test_up_command_agents_none(
        self,
        mock_config,
        mock_tempdir,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        mock_setup_agents,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command with agents=none option."""
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        mock_wait_gateway.return_value = True

        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        mock_subprocess.return_value = Mock(returncode=0)

        # Mock Config class
        mock_cfg_instance = Mock()
        mock_cfg_instance.agents = [Mock(name="test-agent")]
        mock_cfg_instance.registries = {}
        mock_config.return_value = mock_cfg_instance

        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )
        env_file = tmp_path / ".env"
        env_file.write_text("")

        up_command(
            project_dir=tmp_path,
            detach=True,
            fresh=False,
            wait_ready=True,
            agents_mode=AgentStartMode.none,  # Should skip agent setup
            no_langfuse=False,
            env_file=None,
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

        # Should call setup_agents with none mode which will skip actual agent setup
        mock_setup_agents.assert_called_once_with(
            mock_cfg_instance, tmp_path, AgentStartMode.none
        )

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.setup_agents_from_config")
    @patch("agentsystems_sdk.commands.up.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    @patch("agentsystems_sdk.commands.up.Config")
    def test_up_command_no_langfuse(
        self,
        mock_config,
        mock_tempdir,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        mock_setup_agents,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command with --no-langfuse flag."""
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        mock_wait_gateway.return_value = True

        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        mock_subprocess.return_value = Mock(returncode=0)

        # Mock Config class
        mock_cfg_instance = Mock()
        mock_cfg_instance.agents = [Mock(name="test-agent")]
        mock_cfg_instance.registries = {}
        mock_config.return_value = mock_cfg_instance

        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )
        env_file = tmp_path / ".env"
        env_file.write_text("")

        up_command(
            project_dir=tmp_path,
            detach=True,
            fresh=False,
            wait_ready=True,
            agents_mode=AgentStartMode.all,
            no_langfuse=True,  # Should pass langfuse=False to compose_args
            env_file=None,
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

        # Verify compose_args was called with langfuse=False
        mock_compose_args.assert_called_once_with(tmp_path, langfuse=False)

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.Config")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    def test_up_command_invalid_config(
        self,
        mock_tempdir,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_config,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command with invalid config file."""
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )

        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        mock_subprocess.return_value = Mock(returncode=0)

        # Make Config raise an exception
        mock_config.side_effect = ValueError("Invalid config")

        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text("invalid: yaml: content")
        env_file = tmp_path / ".env"
        env_file.write_text("")

        with pytest.raises(typer.Exit):
            up_command(
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

    @patch("agentsystems_sdk.commands.up.subprocess.run")
    @patch("agentsystems_sdk.commands.up.setup_agents_from_config")
    @patch("agentsystems_sdk.commands.up.wait_for_gateway_ready")
    @patch("agentsystems_sdk.commands.up.run_command_with_env")
    @patch("agentsystems_sdk.commands.up.compose_args")
    @patch("agentsystems_sdk.commands.up.ensure_docker_installed")
    @patch("agentsystems_sdk.commands.up.tempfile.TemporaryDirectory")
    @patch("agentsystems_sdk.commands.up.Config")
    def test_up_command_with_custom_env_file(
        self,
        mock_config,
        mock_tempdir,
        mock_ensure_docker,
        mock_compose_args,
        mock_run_command,
        mock_wait_gateway,
        mock_setup_agents,
        mock_subprocess,
        tmp_path,
    ):
        """Test up command with custom --env-file."""
        compose_file = tmp_path / "docker-compose.yml"
        mock_compose_args.return_value = (
            compose_file,
            ["docker-compose", "-f", str(compose_file)],
        )
        mock_wait_gateway.return_value = True

        mock_temp = MagicMock()
        mock_temp.name = str(tmp_path / "docker-config")
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=None)
        mock_tempdir.return_value = mock_temp

        mock_subprocess.return_value = Mock(returncode=0)

        # Mock Config class
        mock_cfg_instance = Mock()
        mock_cfg_instance.agents = [Mock(name="test-agent")]
        mock_cfg_instance.registries = {}
        mock_config.return_value = mock_cfg_instance

        config_path = tmp_path / "agentsystems-config.yml"
        config_path.write_text(
            """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: test-agent
    registry_connection: dockerhub
    repo: test/agent
    tag: latest
"""
        )

        # Create custom env file
        custom_env = tmp_path / "custom.env"
        custom_env.write_text("CUSTOM_VAR=custom_value")

        # No default .env file

        up_command(
            project_dir=tmp_path,
            detach=True,
            fresh=False,
            wait_ready=True,
            agents_mode=AgentStartMode.all,
            no_langfuse=False,
            env_file=custom_env,  # Use custom env file
            agent_control_plane_version=None,
            agentsystems_ui_version=None,
        )

        # Should succeed even without default .env
        mock_setup_agents.assert_called_once()

        # Verify custom env file was used in compose command
        call_args = mock_run_command.call_args_list
        env_file_used = False
        for call in call_args:
            if "--env-file" in str(call):
                env_file_used = True
                break
        assert env_file_used
