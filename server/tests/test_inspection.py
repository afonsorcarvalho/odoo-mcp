import pytest


def test_odoo_metadata_calls_get_metadata(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return [{
            "id": 7,
            "xmlid": "base.partner_admin",
            "noupdate": False,
            "create_uid": [1, "Admin"],
            "create_date": "2024-01-01",
            "write_uid": [1, "Admin"],
            "write_date": "2024-01-02",
        }]

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_metadata_impl("res.partner", [7])
    assert captured["call"] == ("res.partner", "get_metadata", [[7]], None)
    assert out[0]["xmlid"] == "base.partner_admin"


def test_odoo_view_get_default_returns_summary(monkeypatch):
    fake_response = {
        "name": "res.partner.form",
        "view_id": 42,
        "type": "form",
        "arch": '<form><sheet><group><field name="name" required="1"/></group></sheet></form>',
        "fields": {"name": {"type": "char", "string": "Name"}},
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        return fake_response

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_view_get_impl("res.partner", "form")
    assert out["model"] == "res.partner"
    assert out["view_type"] == "form"
    assert out["view_id"] == 42
    assert out["name"] == "res.partner.form"
    assert out["fields_summary"] == [{"name": "name", "required": "1"}]
    assert "arch" not in out
    assert "fields" not in out


def test_odoo_view_get_raw_includes_arch_and_fields(monkeypatch):
    fake_response = {
        "name": "x", "view_id": 1, "type": "form",
        "arch": "<form/>", "fields": {"a": {}},
    }
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", lambda *a, **k: fake_response)
    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_view_get_impl("m", "form", raw=True)
    assert out["arch"] == "<form/>"
    assert out["fields"] == {"a": {}}


def test_odoo_modules_list_default_state_installed(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["model"] = model
        captured["method"] = method
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [{"id": 1, "name": "base", "state": "installed"}]

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_modules_list_impl()
    assert captured["model"] == "ir.module.module"
    assert captured["method"] == "search_read"
    assert captured["args"] == [[["state", "=", "installed"]]]
    assert "name" in captured["kwargs"]["fields"]


def test_odoo_modules_list_state_all_skips_filter(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda model, method, args, kwargs=None: captured.update({"args": args}) or [])
    from odoo_mcp_server.tools import inspection
    inspection._odoo_modules_list_impl(state="all")
    assert captured["args"] == [[]]


def test_odoo_modules_list_pattern_appends_ilike(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda model, method, args, kwargs=None: captured.update({"args": args}) or [])
    from odoo_mcp_server.tools import inspection
    inspection._odoo_modules_list_impl(state="installed", pattern="account")
    assert captured["args"] == [[["state", "=", "installed"], ["name", "ilike", "account"]]]


def test_odoo_menu_tree_recurses_to_depth(monkeypatch):
    """Tree: root -> child -> grandchild. depth=2 includes only root + child."""
    db = {
        "root": {"id": 1, "name": "Root", "sequence": 1, "action": False, "child_id": [2]},
        "child": {"id": 2, "name": "Child", "sequence": 1, "action": False, "child_id": [3]},
        "grand": {"id": 3, "name": "Grand", "sequence": 1, "action": False, "child_id": []},
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        assert model == "ir.ui.menu"
        domain = args[0]
        if domain and domain[0] == ("parent_id", "=", False) or domain == [
            ("parent_id", "=", False), ("active", "=", True)
        ] or domain == [["parent_id", "=", False], ["active", "=", True]]:
            return [db["root"]]
        ids = next((c[2] for c in domain if c[0] == "id"), None)
        if ids == [2]:
            return [db["child"]]
        if ids == [3]:
            return [db["grand"]]
        return []

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_menu_tree_impl(depth=2)
    assert len(out) == 1
    assert out[0]["name"] == "Root"
    assert len(out[0]["children"]) == 1
    assert out[0]["children"][0]["name"] == "Child"
    assert out[0]["children"][0]["children"] == []  # depth cut here


def test_odoo_access_check_returns_allowed(monkeypatch):
    captured = {}
    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return True

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_access_check_impl("res.partner", "read")
    assert out == {"model": "res.partner", "operation": "read", "allowed": True}
    assert captured["call"] == (
        "res.partner", "check_access_rights",
        ["read"],
        {"raise_exception": False},
    )


def test_odoo_access_check_invalid_operation_raises():
    from odoo_mcp_server.tools import inspection
    with pytest.raises(ValueError):
        inspection._odoo_access_check_impl("res.partner", "explode")


def test_odoo_user_groups_default_uses_active_uid(monkeypatch):
    calls = []

    def fake_exec_kw(model, method, args, kwargs=None):
        calls.append((model, method, args, kwargs))
        if model == "res.users" and method == "read":
            return [{
                "id": 2, "login": "admin", "groups_id": [10, 11],
            }]
        if model == "res.groups" and method == "read":
            return [
                {"id": 10, "name": "Settings", "full_name": "Administration / Settings",
                 "category_id": [3, "Administration"]},
                {"id": 11, "name": "User", "full_name": "Sales / User",
                 "category_id": [4, "Sales"]},
            ]
        return []

    def fake_connect():
        return (2, None, "db", "pw")

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    monkeypatch.setattr(transport, "connect", fake_connect)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_user_groups_impl()
    assert out["uid"] == 2
    assert out["login"] == "admin"
    assert {g["name"] for g in out["groups"]} == {"Settings", "User"}
    assert out["groups"][0]["category"] == "Administration"


def test_odoo_company_list_returns_user_companies(monkeypatch):
    def fake_exec_kw(model, method, args, kwargs=None):
        if model == "res.users" and method == "read":
            return [{"id": 2, "company_ids": [1, 2]}]
        if model == "res.company" and method == "read":
            return [
                {"id": 1, "name": "Main Co", "currency_id": [9, "EUR"], "parent_id": False},
                {"id": 2, "name": "Sub Co", "currency_id": [9, "EUR"], "parent_id": [1, "Main Co"]},
            ]
        return []

    def fake_connect():
        return (2, None, "db", "pw")

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    monkeypatch.setattr(transport, "connect", fake_connect)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_company_list_impl()
    assert [c["name"] for c in out] == ["Main Co", "Sub Co"]
    assert out[0]["parent_id"] is None
    assert out[1]["parent_id"] == 1
