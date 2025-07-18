"""Unit test for the `agentsystems run` command (inline JSON payload).

The network layer is fully mocked with `requests-mock`, so the test runs fast
and offline while hitting the new code paths introduced in the CLI.
"""

from typer.testing import CliRunner

from agentsystems_sdk.cli import app


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
