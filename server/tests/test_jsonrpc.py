"""Unit tests for _jsonrpc.py — mock urllib.request.urlopen throughout."""
from __future__ import annotations

import io
import json
import urllib.request
import xmlrpc.client

import pytest


# ---------------------------------------------------------------------------
# Helper: build a fake HTTP response with given JSON body
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, body: dict):
        self._data = json.dumps(body).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _make_urlopen(response_body: dict):
    """Return a monkeypatched urlopen that yields a fake response."""
    def fake_urlopen(req, timeout=None):
        return _FakeResponse(response_body)
    return fake_urlopen


# ---------------------------------------------------------------------------
# _call / authenticate tests
# ---------------------------------------------------------------------------

def test_authenticate_happy_path(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        _make_urlopen({"jsonrpc": "2.0", "result": 7, "id": 1}))

    from odoo_mcp_server import _jsonrpc
    uid = _jsonrpc.authenticate("http://odoo.local", "mydb", "admin", "secret", timeout=10.0)
    assert uid == 7


def test_authenticate_server_error_raises_fault(monkeypatch):
    error_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": 200,
            "message": "Odoo Server Error",
            "data": {
                "name": "odoo.exceptions.AccessDenied",
                "debug": "Traceback...",
                "message": "Access Denied",
            },
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen(error_body))

    from odoo_mcp_server import _jsonrpc
    with pytest.raises(xmlrpc.client.Fault) as exc_info:
        _jsonrpc.authenticate("http://odoo.local", "mydb", "admin", "wrong", timeout=10.0)

    assert "Access Denied" in exc_info.value.faultString


def test_authenticate_zero_uid_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        _make_urlopen({"jsonrpc": "2.0", "result": 0, "id": 1}))

    from odoo_mcp_server import _jsonrpc
    with pytest.raises(RuntimeError, match="no uid"):
        _jsonrpc.authenticate("http://odoo.local", "mydb", "admin", "wrong", timeout=10.0)


# ---------------------------------------------------------------------------
# execute_kw tests
# ---------------------------------------------------------------------------

def test_execute_kw_happy_path(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        _make_urlopen({"jsonrpc": "2.0", "result": [{"id": 1, "name": "Acme"}], "id": 1}))

    from odoo_mcp_server import _jsonrpc
    result = _jsonrpc.execute_kw(
        "http://odoo.local", "mydb", 7, "secret",
        "res.partner", "search_read", [[["name", "=", "Acme"]]], {"fields": ["name"]},
        timeout=10.0,
    )
    assert result == [{"id": 1, "name": "Acme"}]


def test_execute_kw_error_raises_fault(monkeypatch):
    error_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": 200,
            "message": "Odoo Server Error",
            "data": {
                "name": "odoo.exceptions.UserError",
                "message": "No record found",
                "debug": "",
            },
        },
    }
    monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen(error_body))

    from odoo_mcp_server import _jsonrpc
    with pytest.raises(xmlrpc.client.Fault) as exc_info:
        _jsonrpc.execute_kw(
            "http://odoo.local", "mydb", 7, "secret",
            "res.partner", "write", [[1], {"name": "X"}], {},
            timeout=10.0,
        )
    assert "No record found" in exc_info.value.faultString


# ---------------------------------------------------------------------------
# Request body shape tests
# ---------------------------------------------------------------------------

def test_authenticate_body_shape(monkeypatch):
    """Assert that the JSON body sent to urlopen has correct service/method/args."""
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        captured["url"] = req.full_url
        return _FakeResponse({"jsonrpc": "2.0", "result": 3, "id": 1})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    from odoo_mcp_server import _jsonrpc
    _jsonrpc.authenticate("http://odoo.local", "testdb", "bob", "pass", timeout=5.0)

    body = captured["body"]
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "call"
    params = body["params"]
    assert params["service"] == "common"
    assert params["method"] == "authenticate"
    assert params["args"] == ["testdb", "bob", "pass", {}]
    assert captured["url"] == "http://odoo.local/jsonrpc"


def test_execute_kw_body_shape(monkeypatch):
    """Assert execute_kw sends correct service/method/args structure."""
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _FakeResponse({"jsonrpc": "2.0", "result": True, "id": 1})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    from odoo_mcp_server import _jsonrpc
    _jsonrpc.execute_kw(
        "http://odoo.local", "mydb", 7, "pw",
        "sale.order", "write", [[42], {"state": "draft"}], {"context": {"lang": "pt_PT"}},
        timeout=5.0,
    )

    params = captured["body"]["params"]
    assert params["service"] == "object"
    assert params["method"] == "execute_kw"
    assert params["args"] == ["mydb", 7, "pw", "sale.order", "write", [[42], {"state": "draft"}], {"context": {"lang": "pt_PT"}}]
