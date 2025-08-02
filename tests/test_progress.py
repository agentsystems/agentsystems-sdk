"""Unit tests for the lightweight progress tracker helper."""

import threading
from unittest.mock import patch, Mock

import agentsystems_sdk.progress_tracker as pt
import pytest


def test_update_before_init_raises():
    # Reset module state
    pt._thread_id = None
    with pytest.raises(RuntimeError, match="progress_tracker.init"):
        pt.update(percent=10)


def test_init_and_update(monkeypatch):
    sent = []

    def fake_post(path: str, payload):  # noqa: ANN001 – simple stub
        sent.append((path, payload))

    monkeypatch.setattr(pt, "_post", fake_post)

    plan = [{"id": "s1", "label": "Step 1"}]
    pt.init("thread123", plan=plan, gateway_url="http://gw")
    pt.update(percent=50, current="s1", state={"s1": "running"})

    # Two POSTs captured: init + update
    assert len(sent) == 2
    init_path, init_payload = sent[0]
    assert init_path == "http://gw/progress/thread123"
    assert init_payload["progress"]["percent"] == 0
    update_path, update_payload = sent[1]
    assert update_payload["progress"]["percent"] == 50


def test_multiple_updates_no_plan(monkeypatch):
    """init without plan then two updates should yield exactly 2 POSTs."""
    sent = []
    monkeypatch.setattr(pt, "_post", lambda *args, **kwargs: sent.append(args))

    pt.init("tid", gateway_url="http://gw")
    pt.update(percent=10)
    pt.update(percent=20)

    assert len(sent) == 2
    # first update percent 10, second 20
    assert sent[0][1]["progress"]["percent"] == 10
    assert sent[1][1]["progress"]["percent"] == 20


def test_init_with_env_var(monkeypatch):
    """Test that init uses GATEWAY_BASE_URL env var when gateway_url not provided."""
    sent = []
    monkeypatch.setattr(pt, "_post", lambda *args, **kwargs: sent.append(args))
    monkeypatch.setenv("GATEWAY_BASE_URL", "http://env-gateway:9000")

    pt.init("tid123")
    pt.update(percent=25)

    assert len(sent) == 1  # Only update, no plan
    assert sent[0][0] == "http://env-gateway:9000/progress/tid123"


def test_init_with_auth_header(monkeypatch):
    """Test that auth header is stored and used in posts."""
    sent_headers = []

    def capture_post(path, payload):
        # Capture the auth header that would be set
        sent_headers.append(pt._auth_header)

    monkeypatch.setattr(pt, "_post", capture_post)

    pt.init("tid", auth_header="Bearer token123")
    pt.update(percent=30)

    # Check auth header was stored
    assert pt._auth_header == "Bearer token123"
    assert len(sent_headers) == 1


def test_init_with_multiple_step_plan(monkeypatch):
    """Test init with a multi-step plan."""
    sent = []
    monkeypatch.setattr(pt, "_post", lambda *args, **kwargs: sent.append(args))

    plan = [
        {"id": "step1", "label": "First Step"},
        {"id": "step2", "label": "Second Step"},
        {"id": "step3", "label": "Third Step"},
    ]
    pt.init("tid", plan=plan, gateway_url="http://gw")

    assert len(sent) == 1
    path, payload = sent[0]
    assert path == "http://gw/progress/tid"

    progress = payload["progress"]
    assert progress["percent"] == 0
    assert progress["plan"] == plan
    assert progress["current"] == "step1"
    assert progress["state"] == {
        "step1": "queued",
        "step2": "queued",
        "step3": "queued",
    }


def test_init_with_empty_plan(monkeypatch):
    """Test init with empty plan list."""
    sent = []
    monkeypatch.setattr(pt, "_post", lambda *args, **kwargs: sent.append(args))

    pt.init("tid", plan=[], gateway_url="http://gw")

    # Empty plan doesn't trigger a post (if plan: check)
    assert len(sent) == 0

    # But we can still update
    pt.update(percent=50)
    assert len(sent) == 1
    assert sent[0][1]["progress"]["percent"] == 50


def test_post_function_threading():
    """Test that _post creates a daemon thread."""
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        pt._post("http://test/path", {"test": "data"})

        # Verify thread was created with daemon=True
        mock_thread.assert_called_once()
        assert mock_thread.call_args.kwargs["daemon"] is True
        assert mock_thread.call_args.kwargs["target"] is not None

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()


def test_post_function_error_handling():
    """Test that _post silently handles exceptions."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("Network error")

        # Should not raise
        pt._post("http://test/path", {"test": "data"})

        # Wait a bit for thread to execute
        import time

        time.sleep(0.1)


def test_thread_safety_concurrent_updates(monkeypatch):
    """Test that concurrent updates work correctly."""
    sent = []
    monkeypatch.setattr(pt, "_post", lambda *args, **kwargs: sent.append(args))

    pt.init("tid", gateway_url="http://gw")

    # Create multiple threads that update concurrently
    threads = []
    for i in range(5):
        t = threading.Thread(target=lambda i=i: pt.update(percent=i * 10))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Should have 5 updates
    assert len(sent) == 5

    # Check all percentages are present (order may vary)
    percentages = {args[1]["progress"]["percent"] for args in sent}
    assert percentages == {0, 10, 20, 30, 40}
