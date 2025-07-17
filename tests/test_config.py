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
