"""Unit tests for odoo_add_profile tool — transport_flag parameter (T4)."""
from __future__ import annotations

import json
import pytest


def _patch_profiles(monkeypatch, tmp_path):
    """Redirect profiles storage to tmp_path and stub out keyring."""
    from odoo_mcp_server import profiles as mod

    monkeypatch.setattr(mod, "PROFILES_PATH", str(tmp_path / "profiles.json"))
    monkeypatch.setattr(mod, "SECRETS_PATH", str(tmp_path / "secrets.json"))
    monkeypatch.setattr(mod, "_KEYRING_OK", False)
    monkeypatch.setattr(mod, "_adhoc_state", {"profile": None})

    return mod


def test_odoo_add_profile_default_transport_is_xmlrpc(monkeypatch, tmp_path):
    """odoo_add_profile without transport_flag stores xmlrpc."""
    from odoo_mcp_server import profiles as mod, transport
    mod_profiles = _patch_profiles(monkeypatch, tmp_path)

    # Stub set_active so it doesn't touch disk beyond what _patch_profiles covers
    # and stub transport._state to avoid real transport side effects
    monkeypatch.setattr(transport, "_state", {})

    calls = {}

    orig_set_profile = mod_profiles.set_profile

    def spy_set_profile(name, url, db, user, password, transport=None):
        calls["transport"] = transport
        orig_set_profile(name, url, db, user, password, transport=transport)

    monkeypatch.setattr(mod_profiles, "set_profile", spy_set_profile)

    from odoo_mcp_server.tools.auth import register
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)

    # Find the tool function
    tool_fn = None
    for name, tool in mcp._tool_manager._tools.items():
        if name == "odoo_add_profile":
            tool_fn = tool.fn
            break
    assert tool_fn is not None, "odoo_add_profile tool not registered"

    tool_fn(name="myprofile", url="http://odoo.local", db="mydb", user="admin",
            password="secret", activate=False)

    assert calls["transport"] is None  # passed through as None, profiles.set_profile defaults to xmlrpc
    p = mod_profiles.get_profile("myprofile")
    assert p is not None
    assert p["transport"] == "xmlrpc"


def test_odoo_add_profile_jsonrpc_transport(monkeypatch, tmp_path):
    """odoo_add_profile with transport_flag='jsonrpc' stores jsonrpc."""
    from odoo_mcp_server import profiles as mod, transport
    _patch_profiles(monkeypatch, tmp_path)
    monkeypatch.setattr(transport, "_state", {})

    from odoo_mcp_server.tools.auth import register
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)

    tool_fn = None
    for name, tool in mcp._tool_manager._tools.items():
        if name == "odoo_add_profile":
            tool_fn = tool.fn
            break
    assert tool_fn is not None

    tool_fn(name="jrpc", url="http://odoo.local", db="mydb", user="admin",
            password="secret", activate=False, transport_flag="jsonrpc")

    p = mod.get_profile("jrpc")
    assert p is not None
    assert p["transport"] == "jsonrpc"


def test_odoo_add_profile_invalid_transport_raises(monkeypatch, tmp_path):
    """odoo_add_profile with invalid transport_flag raises ValueError."""
    from odoo_mcp_server import profiles as mod, transport
    _patch_profiles(monkeypatch, tmp_path)
    monkeypatch.setattr(transport, "_state", {})

    from odoo_mcp_server.tools.auth import register
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("test")
    register(mcp)

    tool_fn = None
    for name, tool in mcp._tool_manager._tools.items():
        if name == "odoo_add_profile":
            tool_fn = tool.fn
            break
    assert tool_fn is not None

    with pytest.raises(ValueError, match="invalid transport"):
        tool_fn(name="badprofile", url="http://odoo.local", db="mydb", user="admin",
                password="secret", activate=False, transport_flag="soap")
