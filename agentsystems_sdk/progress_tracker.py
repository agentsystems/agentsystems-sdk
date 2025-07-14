"""Lightweight progress-reporting helper for AgentSystems agents.

Usage::

    from agentsystems_sdk import progress_tracker as pt

    steps = [
        {"id": "build_dict", "label": "Build DDQ Dictionary"},
        {"id": "create_folder", "label": "Create Output Folder"},
        # ...
    ]

    pt.init(thread_id, plan=steps, auth_header=request.headers.get("Authorization"))

    # later in the run...
    pt.update(percent=12, current="create_folder", state={"build_dict": "completed"})

The helper is transport-agnostic: it simply POSTs the JSON you provide to the
Gateway `/progress/{thread_id}` endpoint. Calls are fire-and-forget so they will
never slow down the agent execution path.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

import requests

_GATEWAY_ENV_VAR = "GATEWAY_BASE_URL"
_DEFAULT_GATEWAY = "http://gateway:8080"  # container-internal default

_thread_id: Optional[str] = None
_gateway_url: str = _DEFAULT_GATEWAY
_auth_header: Optional[str] = None

_lock = threading.Lock()


def _post(path: str, payload: Dict[str, Any]):
    """Fire-and-forget POST in a daemon thread (2-second timeout)."""

    def _worker():
        try:
            headers = {"Content-Type": "application/json"}
            if _auth_header:
                headers["Authorization"] = _auth_header
            requests.post(path, json=payload, headers=headers, timeout=2)
        except Exception:
            # Silently ignore network errors – progress reporting is best-effort.
            pass

    threading.Thread(target=_worker, daemon=True).start()


def init(
    thread_id: str,
    *,
    plan: Optional[List[Dict[str, Any]]] = None,
    gateway_url: Optional[str] = None,
    auth_header: Optional[str] = None,
):
    """Initialise the tracker and optionally send the initial *plan* payload.

    Parameters
    ----------
    thread_id:
        The UUID provided by the Gateway in the ``X-Thread-Id`` header.
    plan:
        Optional ordered list of step dictionaries, each at minimum having
        ``id`` and ``label`` keys. If provided, ``init`` will immediately POST a
        JSON blob like::

            {
              "progress": {
                "percent": 0,
                "plan": [...],
                "state": {step["id"]: "queued" for step in plan},
                "current": plan[0]["id"]
              }
            }

    gateway_url:
        Override the Gateway base URL. Defaults to
        ``$GATEWAY_BASE_URL`` env var or ``http://gateway:8080``.
    auth_header:
        Optional ``Authorization`` header value (e.g. same Bearer token the
        gateway forwarded). If provided, it is attached to every POST.
    """
    global _thread_id, _gateway_url, _auth_header

    with _lock:
        _thread_id = thread_id
        _gateway_url = gateway_url or os.getenv(_GATEWAY_ENV_VAR, _DEFAULT_GATEWAY)
        _auth_header = auth_header

    if plan:
        # Build initial state map with every step queued.
        state_map = {step["id"]: "queued" for step in plan}
        first_id = plan[0]["id"] if plan else None
        payload = {
            "progress": {
                "percent": 0,
                "plan": plan,
                "state": state_map,
                "current": first_id,
            }
        }
        _post(f"{_gateway_url}/progress/{thread_id}", payload)


def update(**fields: Any):
    """Send a progress *delta* JSON blob.

    Example::

        update(percent=30, current="step2", state={"step1": "completed"})

    Any keyword arguments are inserted under the top-level ``progress`` key. The
    helper does *not* merge or patch server state – it simply POSTs whatever you
    pass it.
    """
    if not _thread_id:
        raise RuntimeError("progress_tracker.init(thread_id) must be called first")

    payload = {"progress": fields}
    _post(f"{_gateway_url}/progress/{_thread_id}", payload)
