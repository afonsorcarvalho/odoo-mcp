"""Live Phase 1 smoke. Set ODOO_TEST_LIVE=1 to run."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def admin_id():
    from odoo_mcp_server import transport
    rows = transport.exec_kw(
        "ir.model.data",
        "search_read",
        [[["module", "=", "base"], ["name", "=", "user_admin"]]],
        {"fields": ["res_id"], "limit": 1},
    )
    if not rows:
        pytest.skip("base.user_admin xmlid not found")
    user_rows = transport.exec_kw(
        "res.users", "read", [[rows[0]["res_id"]]], {"fields": ["partner_id"]}
    )
    return user_rows[0]["partner_id"][0]


def test_view_get_form(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_view_get_impl
    out = _odoo_view_get_impl("res.partner", "form")
    assert out["fields_summary"], "expected non-empty fields_summary"


def test_menu_tree_minimum_depth(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_menu_tree_impl
    tree = _odoo_menu_tree_impl(depth=2)
    assert tree, "expected at least one root menu"


def test_modules_list_contains_base(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_modules_list_impl
    mods = _odoo_modules_list_impl(state="installed", pattern="base")
    assert any(m["name"] == "base" for m in mods)


def test_access_check_read_partner(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_access_check_impl
    out = _odoo_access_check_impl("res.partner", "read")
    assert out["allowed"] is True


def test_user_groups_returns_admin_groups(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_user_groups_impl
    out = _odoo_user_groups_impl()
    assert out["groups"], "admin must have groups"


def test_company_list_at_least_one(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_company_list_impl
    out = _odoo_company_list_impl()
    assert len(out) >= 1


def test_metadata_resolves_xmlid(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_metadata_impl
    rows = _odoo_metadata_impl("res.partner", [admin_id])
    assert rows[0].get("xmlid") or rows[0].get("xmlids")


def test_default_get_returns_dict(admin_id):
    from odoo_mcp_server.tools.workflow import _odoo_default_get_impl
    out = _odoo_default_get_impl("res.partner")
    assert isinstance(out, dict)


def test_copy_then_unlink(admin_id):
    from odoo_mcp_server import transport
    from odoo_mcp_server.tools.workflow import _odoo_copy_impl
    new_id = _odoo_copy_impl("res.partner", admin_id, default={"name": "MCP smoke copy"})
    try:
        assert isinstance(new_id, int)
        rows = transport.exec_kw("res.partner", "read", [[new_id]], {"fields": ["name"]})
        assert rows[0]["name"].startswith("MCP smoke copy")
    finally:
        transport.exec_kw("res.partner", "unlink", [[new_id]], None)


def test_onchange_company_type():
    from odoo_mcp_server.tools.workflow import _odoo_onchange_impl
    out = _odoo_onchange_impl(
        "res.partner",
        {"company_type": "company"},
        "company_type",
    )
    assert isinstance(out, dict)
