"""Unit tests for profiles.py transport field support."""
from __future__ import annotations

import json
import os
import pytest


# ---------------------------------------------------------------------------
# Helpers: patch profiles to use tmp dirs so tests don't touch real files
# ---------------------------------------------------------------------------

def _patch_profiles(monkeypatch, tmp_path):
    """Redirect profiles storage to tmp_path and stub out keyring."""
    profiles_path = str(tmp_path / "odoo-mcp.profiles.json")
    secrets_path = str(tmp_path / "odoo-mcp.profiles.secrets.json")

    from odoo_mcp_server import profiles as mod

    monkeypatch.setattr(mod, "PROFILES_PATH", profiles_path)
    monkeypatch.setattr(mod, "SECRETS_PATH", secrets_path)
    monkeypatch.setattr(mod, "_KEYRING_OK", False)

    # Reset in-memory adhoc state
    monkeypatch.setattr(mod, "_adhoc_state", {"profile": None})

    return mod


# ---------------------------------------------------------------------------
# T1 tests
# ---------------------------------------------------------------------------

def test_set_profile_without_transport_defaults_to_xmlrpc(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    mod.set_profile("myprofile", "http://odoo.local", "mydb", "admin", "secret")
    p = mod.get_profile("myprofile")

    assert p is not None
    assert p["transport"] == "xmlrpc"


def test_set_profile_with_jsonrpc_transport(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    mod.set_profile("myprofile", "http://odoo.local", "mydb", "admin", "secret",
                    transport="jsonrpc")
    p = mod.get_profile("myprofile")

    assert p is not None
    assert p["transport"] == "jsonrpc"


def test_set_profile_with_xmlrpc_transport_explicit(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    mod.set_profile("myprofile", "http://odoo.local", "mydb", "admin", "secret",
                    transport="xmlrpc")
    p = mod.get_profile("myprofile")

    assert p is not None
    assert p["transport"] == "xmlrpc"


def test_set_profile_invalid_transport_raises(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="invalid transport"):
        mod.set_profile("myprofile", "http://odoo.local", "mydb", "admin", "secret",
                        transport="soap")


def test_set_profile_none_transport_keeps_existing(monkeypatch, tmp_path):
    """Updating with transport=None preserves previously set transport."""
    mod = _patch_profiles(monkeypatch, tmp_path)

    mod.set_profile("myprofile", "http://odoo.local", "mydb", "admin", "secret",
                    transport="jsonrpc")
    # Update URL, keep transport implicitly
    mod.set_profile("myprofile", "http://odoo2.local", "mydb", "admin", None,
                    transport=None)
    p = mod.get_profile("myprofile")

    assert p is not None
    assert p["transport"] == "jsonrpc"
    assert p["url"] == "http://odoo2.local"


def test_get_profile_missing_transport_in_stored_data_defaults_xmlrpc(monkeypatch, tmp_path):
    """Old profiles without 'transport' key should default to 'xmlrpc'."""
    mod = _patch_profiles(monkeypatch, tmp_path)

    # Write a profile manually without transport field (simulating old format)
    data = {
        "profiles": {
            "oldprofile": {"url": "http://old.local", "db": "db1", "user": "admin"}
        },
        "active": "oldprofile",
    }
    with open(mod.PROFILES_PATH, "w") as f:
        json.dump(data, f)
    # Write password to fallback secrets
    with open(mod.SECRETS_PATH, "w") as f:
        json.dump({"oldprofile": "secret"}, f)

    p = mod.get_profile("oldprofile")
    assert p is not None
    assert p["transport"] == "xmlrpc"


def test_list_profiles_includes_transport(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    mod.set_profile("alpha", "http://a.local", "db_a", "admin", "s1", transport="xmlrpc")
    mod.set_profile("beta", "http://b.local", "db_b", "admin", "s2", transport="jsonrpc")

    listing = mod.list_profiles()
    by_name = {p["name"]: p for p in listing}

    assert by_name["alpha"]["transport"] == "xmlrpc"
    assert by_name["beta"]["transport"] == "jsonrpc"


def test_list_profiles_old_entry_defaults_xmlrpc(monkeypatch, tmp_path):
    mod = _patch_profiles(monkeypatch, tmp_path)

    # Write without transport
    data = {
        "profiles": {
            "legacy": {"url": "http://x.local", "db": "db", "user": "u"}
        },
        "active": None,
    }
    with open(mod.PROFILES_PATH, "w") as f:
        json.dump(data, f)

    listing = mod.list_profiles()
    assert listing[0]["transport"] == "xmlrpc"
