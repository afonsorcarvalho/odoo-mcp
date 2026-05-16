"""Unit tests for transport.py dispatch logic (T3).

Tests that exec_kw dispatches to models.execute_kw for xmlrpc profiles
and to _jsonrpc.execute_kw for jsonrpc profiles.
"""
from __future__ import annotations

import pytest
import xmlrpc.client


# ---------------------------------------------------------------------------
# Helpers: build a minimal active-creds environment
# ---------------------------------------------------------------------------

def _setup_profile(monkeypatch, transport_kind: str):
    """Make transport._active_creds() return a fake profile with given transport."""
    from odoo_mcp_server import transport

    # Patch _active_creds to return a fixed tuple without touching real profiles
    def fake_active_creds():
        return ("testprofile", "http://odoo.local", "testdb", "admin", "secret", transport_kind)

    monkeypatch.setattr(transport, "_active_creds", fake_active_creds)

    # Clear any cached state
    transport._state.clear()


# ---------------------------------------------------------------------------
# T3: xmlrpc profile dispatches to models.execute_kw
# ---------------------------------------------------------------------------

def test_exec_kw_xmlrpc_calls_models_execute_kw(monkeypatch):
    from odoo_mcp_server import transport, _jsonrpc

    _setup_profile(monkeypatch, "xmlrpc")

    # Fake models proxy
    models_calls = []

    class FakeModels:
        def execute_kw(self, db, uid, password, model, method, args, kwargs):
            models_calls.append((db, uid, password, model, method, args, kwargs))
            return [{"id": 1}]

    # Patch connect() to inject xmlrpc state
    def fake_connect():
        transport._state["testprofile"] = {
            "uid": 5,
            "models": FakeModels(),
            "transport": "xmlrpc",
            "url": "http://odoo.local",
        }
        return 5, transport._state["testprofile"]["models"], "testdb", "secret"

    monkeypatch.setattr(transport, "connect", fake_connect)

    result = transport.exec_kw("res.partner", "search_read", [[]], {"fields": ["name"]})

    assert result == [{"id": 1}]
    assert len(models_calls) == 1
    call = models_calls[0]
    assert call[3] == "res.partner"
    assert call[4] == "search_read"


def test_exec_kw_jsonrpc_calls_jsonrpc_execute_kw(monkeypatch):
    from odoo_mcp_server import transport, _jsonrpc

    _setup_profile(monkeypatch, "jsonrpc")

    jsonrpc_calls = []

    def fake_jsonrpc_execute_kw(url, db, uid, password, model, method, args, kwargs, timeout):
        jsonrpc_calls.append((url, db, uid, password, model, method, args, kwargs))
        return [{"id": 2, "name": "Beta"}]

    monkeypatch.setattr(_jsonrpc, "execute_kw", fake_jsonrpc_execute_kw)

    # Patch connect() to inject jsonrpc state
    def fake_connect():
        transport._state["testprofile"] = {
            "uid": 7,
            "models": None,
            "transport": "jsonrpc",
            "url": "http://odoo.local",
        }
        return 7, None, "testdb", "secret"

    monkeypatch.setattr(transport, "connect", fake_connect)

    result = transport.exec_kw("res.partner", "search_read", [[]], {"fields": ["name"]})

    assert result == [{"id": 2, "name": "Beta"}]
    assert len(jsonrpc_calls) == 1
    call = jsonrpc_calls[0]
    assert call[0] == "http://odoo.local"
    assert call[4] == "res.partner"
    assert call[5] == "search_read"


# ---------------------------------------------------------------------------
# T3: connect() for jsonrpc authenticates via _jsonrpc.authenticate
# ---------------------------------------------------------------------------

def test_connect_jsonrpc_uses_jsonrpc_authenticate(monkeypatch):
    from odoo_mcp_server import transport, _jsonrpc

    _setup_profile(monkeypatch, "jsonrpc")

    auth_calls = []

    def fake_authenticate(url, db, login, password, timeout):
        auth_calls.append((url, db, login, password))
        return 11

    monkeypatch.setattr(_jsonrpc, "authenticate", fake_authenticate)

    uid, models, db, pw = transport.connect()

    assert uid == 11
    assert models is None
    assert len(auth_calls) == 1
    assert auth_calls[0] == ("http://odoo.local", "testdb", "admin", "secret")


def test_exec_kw_falls_back_to_jsonrpc_on_marshal_none_fault(monkeypatch):
    """XMLRPC profile: server-side 'cannot marshal None' fault → retry via JSON-RPC."""
    from odoo_mcp_server import transport, _jsonrpc

    _setup_profile(monkeypatch, "xmlrpc")
    transport._warned_marshal_fallback = False

    class FailingModels:
        def execute_kw(self, *a, **kw):
            raise xmlrpc.client.Fault(
                1,
                "TypeError: cannot marshal None unless allow_none is enabled",
            )

    def fake_connect():
        transport._state["testprofile"] = {
            "uid": 9,
            "models": FailingModels(),
            "transport": "xmlrpc",
            "url": "http://odoo.local",
        }
        return 9, transport._state["testprofile"]["models"], "testdb", "secret"

    monkeypatch.setattr(transport, "connect", fake_connect)

    jsonrpc_calls = []

    def fake_jsonrpc_execute_kw(url, db, uid, password, model, method, args, kwargs, timeout):
        jsonrpc_calls.append((url, db, uid, model, method))
        return {"type": "ir.actions.act_window", "res_id": None}

    monkeypatch.setattr(_jsonrpc, "execute_kw", fake_jsonrpc_execute_kw)

    result = transport.exec_kw("sale.order", "action_confirm", [[1]], {})

    assert result == {"type": "ir.actions.act_window", "res_id": None}
    assert len(jsonrpc_calls) == 1
    assert jsonrpc_calls[0] == ("http://odoo.local", "testdb", 9, "sale.order", "action_confirm")


def test_exec_kw_non_marshal_fault_propagates(monkeypatch):
    """Other XMLRPC faults must NOT trigger JSON-RPC fallback."""
    from odoo_mcp_server import transport

    _setup_profile(monkeypatch, "xmlrpc")

    class FailingModels:
        def execute_kw(self, *a, **kw):
            raise xmlrpc.client.Fault(2, "ValidationError: bad data")

    def fake_connect():
        transport._state["testprofile"] = {
            "uid": 1,
            "models": FailingModels(),
            "transport": "xmlrpc",
            "url": "http://odoo.local",
        }
        return 1, transport._state["testprofile"]["models"], "testdb", "secret"

    monkeypatch.setattr(transport, "connect", fake_connect)

    with pytest.raises(xmlrpc.client.Fault):
        transport.exec_kw("res.partner", "create", [{}], {})


def test_connect_xmlrpc_uses_xmlrpc_authenticate(monkeypatch):
    from odoo_mcp_server import transport

    _setup_profile(monkeypatch, "xmlrpc")

    auth_results = []

    class FakeCommon:
        def authenticate(self, db, user, password, opts):
            auth_results.append((db, user))
            return 3

    def fake_proxy(url_base, path):
        if path == "/xmlrpc/2/common":
            return FakeCommon()
        return object()  # models proxy placeholder

    monkeypatch.setattr(transport, "proxy", fake_proxy)

    uid, models, db, pw = transport.connect()

    assert uid == 3
    assert models is not None  # should be a proxy
    assert auth_results == [("testdb", "admin")]
