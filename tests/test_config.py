"""Unit tests for agentsystems_sdk.config module."""

from pathlib import Path

import pytest

from agentsystems_sdk.config import Config

yaml_good = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
    enabled: true
    auth:
      method: none
agents:
  - name: hello
    registry_connection: dockerhub
    repo: agentsystems/hello
    tag: latest
"""

yaml_missing_registry = """
config_version: 1
registry_connections: {}
agents:
  - name: foo
    registry_connection: dockerhub
    repo: x/y
"""


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "agentsystems-config.yml"
    p.write_text(content)
    return p


def test_config_load_success(tmp_path: Path):
    cfg_path = _write_yaml(tmp_path, yaml_good)
    cfg = Config(cfg_path)
    # Validate parsing results
    assert cfg.version == 1
    assert len(cfg.registries) == 1
    assert len(cfg.agents) == 1
    assert cfg.images() == ["docker.io/agentsystems/hello:latest"]


def test_config_validation_error(tmp_path: Path):
    cfg_path = _write_yaml(tmp_path, yaml_missing_registry)
    with pytest.raises(ValueError):
        Config(cfg_path)


# ---------------------------------------------------------------------------
# Additional edge-case and happy-path tests (merged formerly test_config_extra)
# ---------------------------------------------------------------------------

yaml_no_agents = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
"""

yaml_empty_registries = """
config_version: 1
registry_connections: {}
agents:
  - name: foo
    image: docker.io/agentsystems/foo:latest
"""

yaml_shorthand_default = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    registry_connection: dockerhub
    repo: agentsystems/foo
"""

yaml_shorthand_tag = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    registry_connection: dockerhub
    repo: agentsystems/foo
    tag: v1
"""

yaml_enabled_flag = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
    enabled: true
  ghcr:
    url: ghcr.io
    enabled: false
agents:
  - name: foo
    registry_connection: dockerhub
    repo: agentsystems/foo
"""


def test_no_agents(tmp_path: Path):
    # Empty agent list should be allowed for onboarding
    config = Config(_write_yaml(tmp_path, yaml_no_agents))
    assert config.agents == []


def test_empty_registries(tmp_path: Path):
    # Empty registry dict should be allowed for onboarding
    config = Config(_write_yaml(tmp_path, yaml_empty_registries))
    assert config.registries == {}


def test_shorthand_default_tag(tmp_path: Path):
    cfg = Config(_write_yaml(tmp_path, yaml_shorthand_default))
    assert cfg.images() == ["docker.io/agentsystems/foo:latest"]


def test_shorthand_explicit_tag(tmp_path: Path):
    cfg = Config(_write_yaml(tmp_path, yaml_shorthand_tag))
    assert cfg.images() == ["docker.io/agentsystems/foo:v1"]


def test_enabled_registries(tmp_path: Path):
    cfg = Config(_write_yaml(tmp_path, yaml_enabled_flag))
    names = [r.name for r in cfg.enabled_registries()]
    assert names == ["dockerhub"]


# ---------------------------------------------------------------------------
# Agent declaration variant tests
# ---------------------------------------------------------------------------

yaml_explicit_image = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    image: docker.io/agentsystems/foo:123
"""


def test_explicit_image_variant(tmp_path: Path):
    cfg = Config(_write_yaml(tmp_path, yaml_explicit_image))
    assert cfg.images() == ["docker.io/agentsystems/foo:123"]


yaml_missing_repo = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    registry_connection: dockerhub
    # repo missing
"""


def test_missing_repo_key(tmp_path: Path):
    with pytest.raises(ValueError):
        Config(_write_yaml(tmp_path, yaml_missing_repo))
