"""Tests for the `agentsystems artifacts-path` command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import agentsystems_sdk.cli as cli

runner = CliRunner()


def _run_cli(*args: str, env: dict[str, str] | None = None):
    return runner.invoke(cli.app, list(args), env=env)


def test_missing_env_vars_causes_error(monkeypatch):
    monkeypatch.delenv("AGENT_NAME", raising=False)

    res = _run_cli("artifacts-path")
    assert res.exit_code != 0
    assert "AGENT_NAME not set" in res.output


def test_default_output_path(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "alpha")

    res = _run_cli("artifacts-path")
    assert res.exit_code == 0
    assert res.output.strip() == "/artifacts/alpha/output"


def test_input_flag(monkeypatch):
    monkeypatch.setenv("AGENT_NAME", "alpha")

    res = _run_cli("artifacts-path", "--input")
    assert res.exit_code == 0
    assert res.output.strip() == "/artifacts/alpha/input"


def test_overrides(monkeypatch):
    # env vars present but we override via CLI options
    monkeypatch.setenv("ARTIFACTS_DIR", "/ignored")
    monkeypatch.setenv("AGENT_NAME", "ignored")

    res = _run_cli(
        "artifacts-path",
        "report.json",
        "--thread-id",
        "t123",
        "--agent-name",
        "beta",
    )
    assert res.exit_code == 0
    expected = Path("/artifacts/beta/output/t123/report.json")
    assert res.output.strip() == str(expected)
