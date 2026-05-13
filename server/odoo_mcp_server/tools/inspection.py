"""Inspection / introspection MCP tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import parse_view_arch


def _odoo_metadata_impl(model: str, ids: list[int]) -> list[dict]:
    """Wrap Odoo `get_metadata`. Returns list of metadata dicts per id."""
    return transport.exec_kw(model, "get_metadata", [ids], None)


def _odoo_view_get_impl(
    model: str,
    view_type: str = "form",
    view_id: int | None = None,
    raw: bool = False,
) -> dict:
    """Wrap fields_view_get and reduce to a compact summary."""
    args: list = []
    kwargs: dict = {"view_type": view_type}
    if view_id is not None:
        kwargs["view_id"] = view_id
    res = transport.exec_kw(model, "fields_view_get", args, kwargs)
    out: dict = {
        "model": model,
        "view_type": view_type,
        "view_id": res.get("view_id"),
        "name": res.get("name"),
        "fields_summary": parse_view_arch(res.get("arch") or ""),
    }
    if raw:
        out["arch"] = res.get("arch")
        out["fields"] = res.get("fields")
    return out


def _odoo_modules_list_impl(
    state: str = "installed",
    pattern: str | None = None,
) -> list[dict]:
    """List `ir.module.module` records."""
    domain: list = []
    if state != "all":
        domain.append(["state", "=", state])
    if pattern:
        domain.append(["name", "ilike", pattern])
    return transport.exec_kw(
        "ir.module.module",
        "search_read",
        [domain],
        {
            "fields": ["name", "shortdesc", "state", "installed_version"],
            "order": "name",
        },
    )


_ALLOWED_OPERATIONS = ("read", "write", "create", "unlink")


def _odoo_access_check_impl(
    model: str,
    operation: str = "read",
    raise_exception: bool = False,
) -> dict:
    """Wrap check_access_rights."""
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(
            f"operation must be one of {_ALLOWED_OPERATIONS}, got {operation!r}"
        )
    allowed = transport.exec_kw(
        model,
        "check_access_rights",
        [operation],
        {"raise_exception": raise_exception},
    )
    return {"model": model, "operation": operation, "allowed": bool(allowed)}


def _odoo_menu_tree_impl(
    depth: int = 3,
    active_only: bool = True,
) -> list[dict]:
    """Build a depth-bounded tree from ir.ui.menu, starting at root menus."""
    base_filter: list = [["active", "=", True]] if active_only else []
    fields = ["id", "name", "sequence", "action", "child_id"]

    roots = transport.exec_kw(
        "ir.ui.menu",
        "search_read",
        [[["parent_id", "=", False]] + base_filter],
        {"fields": fields, "order": "sequence,name"},
    )

    def build(menu: dict, remaining: int) -> dict:
        out = {
            "id": menu["id"],
            "name": menu["name"],
            "sequence": menu["sequence"],
            "action": menu.get("action") or None,
            "children": [],
        }
        child_ids = menu.get("child_id") or []
        if remaining > 1 and child_ids:
            children = transport.exec_kw(
                "ir.ui.menu",
                "search_read",
                [[["id", "in", child_ids]] + base_filter],
                {"fields": fields, "order": "sequence,name"},
            )
            out["children"] = [build(c, remaining - 1) for c in children]
        return out

    return [build(r, depth) for r in roots]


def _odoo_user_groups_impl(uid: int | None = None) -> dict:
    """List groups for `uid` (defaults to currently authenticated uid)."""
    if uid is None:
        uid, _, _, _ = transport.connect()
    users = transport.exec_kw(
        "res.users", "read", [[uid]], {"fields": ["login", "groups_id"]},
    )
    if not users:
        raise RuntimeError(f"user {uid} not found")
    user = users[0]
    group_ids = user.get("groups_id") or []
    groups = transport.exec_kw(
        "res.groups",
        "read",
        [group_ids],
        {"fields": ["name", "full_name", "category_id"]},
    ) if group_ids else []
    return {
        "uid": user["id"],
        "login": user["login"],
        "groups": [
            {
                "id": g["id"],
                "name": g["name"],
                "full_name": g.get("full_name"),
                "category": (g.get("category_id") or [None, None])[1],
            }
            for g in groups
        ],
    }


def _odoo_company_list_impl() -> list[dict]:
    """List companies the current user has access to."""
    uid, _, _, _ = transport.connect()
    users = transport.exec_kw(
        "res.users", "read", [[uid]], {"fields": ["company_ids"]},
    )
    if not users:
        return []
    company_ids = users[0].get("company_ids") or []
    if not company_ids:
        return []
    companies = transport.exec_kw(
        "res.company",
        "read",
        [company_ids],
        {"fields": ["name", "currency_id", "parent_id"]},
    )
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "currency_id": (c.get("currency_id") or [None])[0],
            "parent_id": (c.get("parent_id") or [None])[0],
        }
        for c in companies
    ]


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_metadata(model: str, ids: list[int]) -> list[dict]:
        """Wrap Odoo `get_metadata`.

        Returns: [{id, xmlid, noupdate, create_uid, create_date, write_uid, write_date}, ...]
        """
        return _odoo_metadata_impl(model, ids)

    @mcp.tool()
    def odoo_view_get(
        model: str,
        view_type: str = "form",
        view_id: int | None = None,
        raw: bool = False,
    ) -> dict:
        """Inspect an Odoo view.

        Default: returns {model, view_type, view_id, name, fields_summary}.
        raw=True: also returns full `arch` (XML) and `fields` dict.
        """
        return _odoo_view_get_impl(model, view_type, view_id, raw)

    @mcp.tool()
    def odoo_modules_list(
        state: str = "installed",
        pattern: str | None = None,
    ) -> list[dict]:
        """List Odoo modules.

        state in ("installed", "uninstalled", "to install", "to upgrade",
        "to remove", "all"). pattern filters by name (ilike).
        """
        return _odoo_modules_list_impl(state, pattern)

    @mcp.tool()
    def odoo_menu_tree(depth: int = 3, active_only: bool = True) -> list[dict]:
        """Build a depth-bounded ir.ui.menu tree starting at roots."""
        return _odoo_menu_tree_impl(depth, active_only)

    @mcp.tool()
    def odoo_access_check(
        model: str,
        operation: str = "read",
        raise_exception: bool = False,
    ) -> dict:
        """Check whether the current user can perform `operation` on `model`."""
        return _odoo_access_check_impl(model, operation, raise_exception)

    @mcp.tool()
    def odoo_user_groups(uid: int | None = None) -> dict:
        """Return {uid, login, groups: [{id, name, full_name, category}]}.

        uid=None uses the currently authenticated user.
        """
        return _odoo_user_groups_impl(uid)

    @mcp.tool()
    def odoo_company_list() -> list[dict]:
        """List companies the current user has access to."""
        return _odoo_company_list_impl()
