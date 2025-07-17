"""Negative-path tests for Config validation logic."""

from pathlib import Path

import pytest

from agentsystems_sdk.config import Config

yaml_bad_version = """
config_version: 2  # unsupported
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    registry_connection: dockerhub
    repo: ag/foo
"""

yaml_unknown_registry = """
config_version: 1
registry_connections:
  dockerhub:
    url: docker.io
agents:
  - name: foo
    registry_connection: ghcr
    repo: ag/foo
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "agentsystems-config.yml"
    p.write_text(content)
    return p


def test_unsupported_version(tmp_path: Path):
    with pytest.raises(ValueError):
        Config(_write(tmp_path, yaml_bad_version))


def test_unknown_registry(tmp_path: Path):
    with pytest.raises(ValueError):
        Config(_write(tmp_path, yaml_unknown_registry))
