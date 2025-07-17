"""Unit tests for the lightweight progress tracker helper."""

import agentsystems_sdk.progress_tracker as pt
import pytest


def test_update_before_init_raises():
    with pytest.raises(RuntimeError):
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
