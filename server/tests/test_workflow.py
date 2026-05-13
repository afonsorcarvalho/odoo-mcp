import pytest


def test_odoo_default_get_explicit_fields(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return {"name": "New", "active": True}

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_default_get_impl("res.partner", ["name", "active"])
    assert captured["call"] == ("res.partner", "default_get", [["name", "active"]], None)
    assert out == {"name": "New", "active": True}


def test_odoo_default_get_none_fetches_all_fields(monkeypatch):
    captured = []

    def fake_exec_kw(model, method, args, kwargs=None):
        captured.append((model, method, args, kwargs))
        if method == "fields_get":
            return {"name": {}, "email": {}}
        if method == "default_get":
            return {"name": "X"}
        raise AssertionError(method)

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_default_get_impl("res.partner", None)
    assert out == {"name": "X"}
    assert captured[0][1] == "fields_get"
    assert captured[1][1] == "default_get"
    # ensures both 'name' and 'email' got passed in
    assert sorted(captured[1][2][0]) == ["email", "name"]


def test_odoo_copy_calls_copy_with_default(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return 99

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_copy_impl("res.partner", 7, default={"name": "Copy of X"})
    assert out == 99
    assert captured["call"] == ("res.partner", "copy", [7, {"name": "Copy of X"}], None)


def test_odoo_copy_default_none(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda m, meth, a, k=None: captured.update({"args": a}) or 1)
    from odoo_mcp_server.tools import workflow
    workflow._odoo_copy_impl("res.partner", 7)
    assert captured["args"] == [7, {}]


def test_odoo_call_button_executes(monkeypatch):
    captured = {}
    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return {"type": "ir.actions.act_window_close"}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_call_button_impl("sale.order", [5], "action_confirm")
    assert out == {"type": "ir.actions.act_window_close"}
    assert captured["call"] == ("sale.order", "action_confirm", [[5]], {})


def test_odoo_call_button_rejects_non_whitelisted_method():
    from odoo_mcp_server.tools import workflow
    with pytest.raises(ValueError, match="must start with"):
        workflow._odoo_call_button_impl("res.partner", [1], "write")


def test_odoo_call_button_passes_kwargs(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda m, meth, a, k=None: captured.update({"kwargs": k}) or True)
    from odoo_mcp_server.tools import workflow
    workflow._odoo_call_button_impl("sale.order", [5], "action_confirm",
                                    kwargs={"context": {"foo": 1}})
    assert captured["kwargs"] == {"context": {"foo": 1}}


def test_odoo_onchange_resolves_field_onchange_from_view(monkeypatch):
    calls = []

    fake_view = {
        "view_id": 42,
        "fields": {
            "company_type": {"on_change": "1"},
            "name": {"on_change": "0"},
        },
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        calls.append((model, method, args, kwargs))
        if method == "fields_view_get":
            return fake_view
        if method == "onchange":
            assert args[0] == []
            assert args[1] == {"company_type": "company"}
            assert args[2] == "company_type"
            assert args[3] == {"company_type": "1", "name": "0"}
            return {"value": {"is_company": True}}
        raise AssertionError(method)

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_onchange_impl(
        "res.partner",
        {"company_type": "company"},
        "company_type",
    )
    assert out == {"value": {"is_company": True}}
    assert calls[0][1] == "fields_view_get"
    assert calls[1][1] == "onchange"
