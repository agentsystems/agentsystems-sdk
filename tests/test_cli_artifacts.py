"""Tests for the `agentsystems artifacts-path` command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import agentsystems_sdk.cli as cli

runner = CliRunner()


def _run_cli(*args: str, env: dict[str, str] | None = None):
    return runner.invoke(cli.app, list(args), env=env)


def test_missing_thread_id_causes_error():
    """Test that missing thread_id argument causes error."""
    res = _run_cli("artifacts-path")
    assert res.exit_code != 0
    assert "Missing argument" in res.output


def test_default_output_path():
    """Test default output path with thread-centric structure."""
    res = _run_cli("artifacts-path", "abc123")
    assert res.exit_code == 0
    assert res.output.strip() == "/artifacts/abc123/out"


def test_input_flag():
    """Test input flag returns 'in' directory."""
    res = _run_cli("artifacts-path", "abc123", "--input")
    assert res.exit_code == 0
    assert res.output.strip() == "/artifacts/abc123/in"


def test_relative_path():
    """Test relative path appending to thread directory."""
    res = _run_cli("artifacts-path", "abc123", "report.json")
    assert res.exit_code == 0
    expected = Path("/artifacts/abc123/out/report.json")
    assert res.output.strip() == str(expected)


def test_input_with_relative_path():
    """Test input flag with relative path."""
    res = _run_cli("artifacts-path", "abc123", "data.txt", "--input")
    assert res.exit_code == 0
    expected = Path("/artifacts/abc123/in/data.txt")
    assert res.output.strip() == str(expected)
