"""Unit tests for the `agentsystems run` command.

The network layer is fully mocked with `requests-mock`, so the tests run fast
and offline while hitting the new code paths introduced in the CLI.
"""

from unittest.mock import patch, Mock

import pytest
import typer
from typer.testing import CliRunner

from agentsystems_sdk.cli import app
from agentsystems_sdk.commands.run import run_command


def test_run_inline_json(requests_mock):  # noqa: D103  (docstring not needed)
    tid = "12345678-1234-5678-1234-567812345678"

    # --- Mock gateway endpoints -------------------------------------------------
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/test-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )
    # Status endpoint returns *completed* on first poll so the loop exits quickly.
    requests_mock.get(
        f"{base}/status/{tid}",
        json={
            "thread_id": tid,
            "state": "completed",
            "progress": {"percent": 100, "current": "done"},
            "error": None,
        },
    )
    requests_mock.get(
        f"{base}/result/{tid}",
        json={"thread_id": tid, "result": {"ok": True}},
    )

    # --- Invoke CLI -------------------------------------------------------------
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "test-agent",
            '{"date":"Oct 20"}',
            "--gateway",
            base,
        ],
    )

    # --- Assertions -------------------------------------------------------------
    assert result.exit_code == 0, result.output
    assert "Invocation finished" in result.output


def test_run_json_file(requests_mock, tmp_path):
    """Test run command with JSON file payload."""
    tid = "test-thread-456"

    # Create a JSON file
    payload_file = tmp_path / "payload.json"
    payload_file.write_text('{"test": "file payload"}')

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/file-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )
    requests_mock.get(
        f"{base}/status/{tid}",
        json={"thread_id": tid, "state": "completed"},
    )
    requests_mock.get(
        f"{base}/result/{tid}",
        json={"result": "success"},
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "file-agent", str(payload_file), "--gateway", base],
    )

    assert result.exit_code == 0
    assert "Invocation finished" in result.output


def test_run_with_token(requests_mock):
    """Test run command with bearer token."""
    tid = "auth-thread-789"

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/auth-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )
    requests_mock.get(
        f"{base}/status/{tid}",
        json={"thread_id": tid, "state": "completed"},
    )
    requests_mock.get(
        f"{base}/result/{tid}",
        json={"result": "authenticated"},
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "auth-agent",
            '{"auth": true}',
            "--gateway",
            base,
            "--token",
            "secret-token",
        ],
    )

    assert result.exit_code == 0
    # Check that Authorization header was sent
    assert (
        requests_mock.last_request.headers.get("Authorization") == "Bearer secret-token"
    )


def test_run_failed_state(requests_mock):
    """Test run command when agent execution fails."""
    tid = "failed-thread-123"

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/fail-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )
    requests_mock.get(
        f"{base}/status/{tid}",
        json={
            "thread_id": tid,
            "state": "failed",
            "error": "Agent crashed",
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "fail-agent", '{"fail": true}', "--gateway", base],
    )

    assert result.exit_code == 1
    assert "Failed: Agent crashed" in result.output


def test_run_invalid_json():
    """Test run command with invalid JSON."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "test-agent", "invalid json", "--gateway", "http://localhost:8080"],
    )

    assert result.exit_code == 1
    assert "Invalid JSON payload" in result.output


def test_run_no_thread_id(requests_mock):
    """Test run command when response has no thread_id."""
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/bad-agent",
        json={"status": "ok"},  # Missing thread_id
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "bad-agent", '{"test": true}', "--gateway", base],
    )

    assert result.exit_code == 1
    assert "No thread_id in response" in result.output


def test_run_with_input_files(requests_mock, tmp_path):
    """Test run command with input files."""
    tid = "file-upload-thread"

    # Create test file
    file1 = tmp_path / "test1.txt"
    file1.write_text("content1")

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/upload-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )
    requests_mock.get(
        f"{base}/status/{tid}",
        json={"thread_id": tid, "state": "completed"},
    )
    requests_mock.get(
        f"{base}/result/{tid}",
        json={"files_received": 1},
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "upload-agent",
            '{"upload": true}',
            "--gateway",
            base,
            "--input-file",
            str(file1),
        ],
    )

    assert result.exit_code == 0
    # The test verifies that file upload path is exercised


def test_run_status_poll_retry(requests_mock):
    """Test run command retries on status poll failure."""
    tid = "retry-thread"

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/retry-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )

    # First status call fails, second succeeds
    responses = [
        {"status_code": 500},  # First call fails
        {"json": {"thread_id": tid, "state": "completed"}},  # Second succeeds
    ]
    requests_mock.get(
        f"{base}/status/{tid}",
        responses,
    )

    requests_mock.get(
        f"{base}/result/{tid}",
        json={"result": "success after retry"},
    )

    runner = CliRunner()
    with patch("agentsystems_sdk.commands.run.time.sleep"):  # Speed up test
        result = runner.invoke(
            app,
            [
                "run",
                "retry-agent",
                '{"retry": true}',
                "--gateway",
                base,
                "--interval",
                "0.1",
            ],
        )

    assert result.exit_code == 0
    assert "Invocation finished" in result.output


def test_run_with_progress_updates(requests_mock):
    """Test run command shows progress updates."""
    tid = "progress-thread"

    # Mock endpoints
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/progress-agent",
        json={
            "thread_id": tid,
            "status_url": f"/status/{tid}",
            "result_url": f"/result/{tid}",
        },
    )

    # Multiple status updates
    responses = [
        {
            "json": {
                "thread_id": tid,
                "state": "running",
                "progress": {"current": "Step 1"},
            }
        },
        {
            "json": {
                "thread_id": tid,
                "state": "running",
                "progress": {"current": "Step 2"},
            }
        },
        {"json": {"thread_id": tid, "state": "completed"}},
    ]
    requests_mock.get(
        f"{base}/status/{tid}",
        responses,
    )

    requests_mock.get(
        f"{base}/result/{tid}",
        json={"result": "done"},
    )

    runner = CliRunner()
    with patch("agentsystems_sdk.commands.run.time.sleep"):  # Speed up test
        result = runner.invoke(
            app,
            [
                "run",
                "progress-agent",
                '{"show": "progress"}',
                "--gateway",
                base,
                "--interval",
                "0.1",
            ],
        )

    assert result.exit_code == 0


def test_run_connection_error(requests_mock):
    """Test run command handles connection errors."""
    base = "http://localhost:8080"
    requests_mock.post(
        f"{base}/invoke/error-agent",
        exc=ConnectionError("Network unreachable"),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "error-agent", '{"error": true}', "--gateway", base],
    )

    assert result.exit_code == 1
    assert (
        "Unexpected error" in result.output
    )  # ConnectionError gets caught as unexpected


def test_run_command_direct_with_bearer_prefix():
    """Test run_command function handles token with Bearer prefix."""
    with patch("agentsystems_sdk.commands.run.requests.post") as mock_post:
        with patch("agentsystems_sdk.commands.run.requests.get") as mock_get:
            with patch("agentsystems_sdk.commands.run.time.sleep"):
                # Setup mocks
                mock_post.return_value.json.return_value = {
                    "thread_id": "test",
                    "status_url": "/status/test",
                    "result_url": "/result/test",
                }
                mock_post.return_value.raise_for_status = Mock()

                mock_get.side_effect = [
                    Mock(json=Mock(return_value={"state": "completed"})),
                    Mock(json=Mock(return_value={"result": "ok"})),
                ]

                # Execute with token that already has Bearer prefix
                run_command(
                    agent="test",
                    payload='{"test": true}',
                    input_files=None,
                    gateway="http://localhost:8080",
                    poll_interval=0.1,
                    token="Bearer already-prefixed",
                )

                # Verify token wasn't double-prefixed
                assert (
                    mock_post.call_args[1]["headers"]["Authorization"]
                    == "Bearer already-prefixed"
                )


def test_run_command_direct_exception_handling():
    """Test run_command function handles unexpected exceptions."""
    with patch("agentsystems_sdk.commands.run.requests.post") as mock_post:
        mock_post.side_effect = Exception("Unexpected error")

        with pytest.raises(typer.Exit) as exc_info:
            run_command(
                agent="test",
                payload='{"test": true}',
                input_files=None,
                gateway="http://localhost:8080",
                poll_interval=0.1,
                token=None,
            )

        assert exc_info.value.exit_code == 1


def test_run_command_request_exception():
    """Test run_command handles requests exceptions."""
    import requests

    with patch("agentsystems_sdk.commands.run.requests.post") as mock_post:
        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(typer.Exit) as exc_info:
            run_command(
                agent="test",
                payload='{"test": true}',
                input_files=None,
                gateway="http://localhost:8080",
                poll_interval=0.1,
                token=None,
            )

        assert exc_info.value.exit_code == 1
