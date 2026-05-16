"""XML-RPC transport, auth caching, and retry logic.

Pure infrastructure — no MCP tool decorators here. Tools live under tools/*.
"""
from __future__ import annotations

import http.client
import logging
import os
import socket
import sys
import time
import xmlrpc.client
from typing import Any

from . import _jsonrpc, profiles

logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("ODOO_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s odoo-mcp %(message)s",
)
log = logging.getLogger("odoo-mcp")


def load_env_file() -> None:
    """Load `~/.claude/odoo-mcp.env` into os.environ for keys not already set."""
    path = os.path.join(os.path.expanduser("~"), ".claude", "odoo-mcp.env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                k = k.strip()
                v = v.strip()
                if k and not os.environ.get(k):
                    os.environ[k] = v
    except Exception as e:
        log.warning("failed loading env file %s: %s", path, e)


def _timeout() -> float:
    try:
        return float(os.environ.get("ODOO_TIMEOUT", "30"))
    except ValueError:
        return 30.0


class _TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: float, use_https: bool):
        super().__init__()
        self._timeout = timeout
        self._use_https = use_https

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        chost, self._extra_headers, _x509 = self.get_host_info(host)
        if self._use_https:
            self._connection = host, http.client.HTTPSConnection(chost, timeout=self._timeout)
        else:
            self._connection = host, http.client.HTTPConnection(chost, timeout=self._timeout)
        return self._connection[1]


_state: dict[str, dict[str, Any]] = {}

_TRANSIENT = (
    xmlrpc.client.ProtocolError,
    ConnectionError,
    socket.timeout,
    OSError,
)


def _active_creds() -> tuple[str, str, str, str, str, str]:
    """Return (name, url, db, user, password, transport)."""
    name = profiles.current_profile_name()
    if not name:
        raise RuntimeError(
            "No active Odoo profile. Use `odoo_add_profile` to create one, "
            "or `odoo_connect_ad_hoc` for a one-shot connection."
        )
    p = profiles.get_profile(name)
    if not p:
        raise RuntimeError(f"active profile '{name}' has no resolvable credentials")
    transport_kind = p.get("transport", "xmlrpc")
    return name, p["url"], p["db"], p["user"], p["password"], transport_kind


def proxy(url_base: str, path: str) -> xmlrpc.client.ServerProxy:
    full = f"{url_base.rstrip('/')}{path}"
    transport = _TimeoutTransport(_timeout(), use_https=full.startswith("https://"))
    return xmlrpc.client.ServerProxy(full, allow_none=True, transport=transport)


def connect() -> tuple[int, xmlrpc.client.ServerProxy | None, str, str]:
    """Authenticate (if needed) and return (uid, models_proxy_or_None, db, password).

    For xmlrpc profiles models_proxy is a ServerProxy.
    For jsonrpc profiles models_proxy is None — use _dispatch_exec_kw() instead.
    """
    name, url, db, user, password, transport_kind = _active_creds()
    cache = _state.get(name)
    if cache is None:
        log.info(
            "authenticating profile=%s db=%s user=%s url=%s transport=%s",
            name, db, user, url, transport_kind,
        )
        if transport_kind == "jsonrpc":
            uid = _jsonrpc.authenticate(url, db, user, password, _timeout())
        else:
            common = proxy(url, "/xmlrpc/2/common")
            uid = common.authenticate(db, user, password, {})
            if not uid:
                raise RuntimeError(
                    f"Odoo authentication failed for profile={name} user={user} db={db}. "
                    "Check credentials and url."
                )
        log.info("authenticated profile=%s uid=%d transport=%s", name, uid, transport_kind)
        models_proxy = proxy(url, "/xmlrpc/2/object") if transport_kind != "jsonrpc" else None
        cache = {
            "uid": uid,
            "models": models_proxy,
            "transport": transport_kind,
            "url": url,
        }
        _state[name] = cache
    return cache["uid"], cache["models"], db, password


def _dispatch_exec_kw(
    model: str, method: str, args: list, kwargs: dict
) -> Any:
    """Inner call that dispatches to XML-RPC or JSON-RPC based on active profile."""
    # Use _active_creds to get transport_kind without relying on cached _state key
    name, url, db, user, password, transport_kind = _active_creds()
    uid, models, db, password = connect()
    if transport_kind == "jsonrpc":
        return _jsonrpc.execute_kw(url, db, uid, password, model, method, args, kwargs, _timeout())
    else:
        return models.execute_kw(db, uid, password, model, method, args, kwargs)


def _is_session_fault(exc: xmlrpc.client.Fault) -> bool:
    msg = (exc.faultString or "").lower()
    return any(s in msg for s in ("accessdenied", "session expired", "sessionexpired"))


def _is_marshal_none_fault(exc: xmlrpc.client.Fault) -> bool:
    """Odoo XMLRPC endpoint refuses to serialize None in responses.

    Triggered by methods (buttons, onchange, default_get...) returning dicts
    with None values. JSON-RPC has no such limit — retry there.
    """
    msg = exc.faultString or ""
    return "cannot marshal None" in msg or "marshal None" in msg


_warned_marshal_fallback = False


def invalidate_active() -> None:
    name = profiles.current_profile_name()
    if name and name in _state:
        del _state[name]


def exec_kw(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    """Execute Odoo method with retry on transient errors and re-auth on stale UID.

    Dispatches to XML-RPC or JSON-RPC depending on the active profile's transport.
    """
    last_exc: Exception | None = None
    reauthed = False
    for attempt in range(3):
        start = time.monotonic()
        try:
            result = _dispatch_exec_kw(model, method, args, kwargs or {})
            log.debug(
                "exec model=%s method=%s args=%d ok dur=%.0fms",
                model, method, len(args), (time.monotonic() - start) * 1000,
            )
            return result
        except xmlrpc.client.Fault as e:
            if not reauthed and _is_session_fault(e):
                log.warning("stale session, re-authenticating: %s", e.faultString)
                invalidate_active()
                reauthed = True
                continue
            if _is_marshal_none_fault(e):
                name, url, db, user, password, transport_kind = _active_creds()
                if transport_kind != "jsonrpc":
                    global _warned_marshal_fallback
                    if not _warned_marshal_fallback:
                        log.warning(
                            "Odoo XMLRPC cannot marshal None in response for "
                            "model=%s method=%s — falling back to JSON-RPC. "
                            "Switch profile %r to transport=jsonrpc to avoid this.",
                            model, method, name,
                        )
                        _warned_marshal_fallback = True
                    uid, _models, _db, _pw = connect()
                    return _jsonrpc.execute_kw(
                        url, db, uid, password, model, method,
                        args, kwargs or {}, _timeout(),
                    )
            log.error("Odoo fault model=%s method=%s: %s", model, method, e.faultString)
            raise
        except _TRANSIENT as e:
            last_exc = e
            log.warning(
                "transient error model=%s method=%s attempt=%d: %s",
                model, method, attempt + 1, e,
            )
            time.sleep(0.5 * (2 ** attempt))
            invalidate_active()
    assert last_exc is not None
    raise last_exc
