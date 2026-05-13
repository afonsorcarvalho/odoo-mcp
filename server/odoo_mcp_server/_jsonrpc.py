"""Minimal stdlib JSON-RPC client for Odoo's /jsonrpc endpoint.

Uses only urllib.request + json — no new dependencies.

Odoo JSON-RPC protocol:
  POST <url>/jsonrpc
  Content-Type: application/json
  Body: {"jsonrpc": "2.0", "method": "call",
         "params": {"service": <svc>, "method": <m>, "args": [...]}, "id": <int>}

Errors are converted to xmlrpc.client.Fault so transport.py's existing
fault-handling and retry logic work unchanged.
"""
from __future__ import annotations

import json
import urllib.request
import xmlrpc.client
from typing import Any

_REQUEST_ID = 1  # monotonic counter is not needed; constant is fine for JSON-RPC 2.0


def _call(url: str, service: str, method: str, args: list, timeout: float) -> Any:
    """POST a JSON-RPC request to <url>/jsonrpc and return the result.

    Raises:
        xmlrpc.client.Fault  – when the server returns {"error": ...}
        ConnectionError / OSError – network-level failures (caught by transport retry)
    """
    endpoint = url.rstrip("/") + "/jsonrpc"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "call",
        "id": _REQUEST_ID,
        "params": {
            "service": service,
            "method": method,
            "args": args,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        # Re-raise as OSError so transport._TRANSIENT catches it
        raise OSError(f"HTTP {e.code} from {endpoint}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(f"URL error connecting to {endpoint}: {e.reason}") from e

    data = json.loads(body)

    if "error" in data:
        err = data["error"]
        err_data = err.get("data", {})
        message = err_data.get("message") or err.get("message") or str(err)
        debug = err_data.get("debug", "")
        fault_string = f"{message}\n{debug}".strip() if debug else message
        raise xmlrpc.client.Fault(faultCode=1, faultString=fault_string)

    return data["result"]


def authenticate(url: str, db: str, login: str, password: str, timeout: float) -> int:
    """Authenticate against Odoo via JSON-RPC. Returns uid (int > 0).

    Raises RuntimeError if authentication succeeds but uid is falsy.
    Raises xmlrpc.client.Fault on server-side auth error.
    """
    result = _call(url, "common", "authenticate", [db, login, password, {}], timeout)
    if not result:
        raise RuntimeError(
            f"Odoo JSON-RPC authentication returned no uid for db={db} user={login}. "
            "Check credentials."
        )
    return int(result)


def execute_kw(
    url: str,
    db: str,
    uid: int,
    password: str,
    model: str,
    method: str,
    args: list,
    kwargs: dict,
    timeout: float,
) -> Any:
    """Call execute_kw on Odoo's object service via JSON-RPC."""
    return _call(
        url,
        "object",
        "execute_kw",
        [db, uid, password, model, method, args, kwargs],
        timeout,
    )
