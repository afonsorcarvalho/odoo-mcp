"""Workflow MCP tools: button calls, onchange, defaults, copy."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import is_button_method


def _odoo_default_get_impl(
    model: str,
    fields: list[str] | None = None,
) -> dict:
    """Wrap default_get(fields). fields=None → all fields from fields_get."""
    if fields is None:
        all_fields = transport.exec_kw(model, "fields_get", [], {"attributes": ["type"]})
        fields = list(all_fields.keys())
    return transport.exec_kw(model, "default_get", [fields], None)


def _odoo_copy_impl(
    model: str,
    id: int,
    default: dict | None = None,
) -> int:
    """Wrap Odoo copy(id, default). Returns the new record id."""
    return transport.exec_kw(model, "copy", [id, default or {}], None)


def _odoo_call_button_impl(
    model: str,
    ids: list[int],
    method: str,
    kwargs: dict | None = None,
) -> Any:
    """Call a button-style method on a recordset.

    Method name must start with action_/button_/toggle_. Returned value is
    whatever Odoo returns — typically True or an ir.actions.* dict.
    """
    if not is_button_method(method):
        raise ValueError(
            f"method {method!r} must start with one of action_/button_/toggle_"
        )
    return transport.exec_kw(model, method, [ids], kwargs or {})


def _odoo_onchange_impl(
    model: str,
    values: dict,
    trigger_field: str,
    view_id: int | None = None,
) -> dict:
    """Run Odoo onchange. Auto-resolves field_onchange spec from form view."""
    view_kwargs: dict = {"view_type": "form"}
    if view_id is not None:
        view_kwargs["view_id"] = view_id
    view = transport.exec_kw(model, "fields_view_get", [], view_kwargs)
    fields_spec = view.get("fields") or {}
    field_onchange = {
        name: str(fdef.get("on_change") or "0")
        for name, fdef in fields_spec.items()
    }
    return transport.exec_kw(
        model,
        "onchange",
        [[], values, trigger_field, field_onchange],
        None,
    )


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_default_get(
        model: str,
        fields: list[str] | None = None,
    ) -> dict:
        """Return Odoo's default values for `fields` on `model`.

        fields=None fetches all field names first via fields_get.
        """
        return _odoo_default_get_impl(model, fields)

    @mcp.tool()
    def odoo_copy(
        model: str,
        id: int,
        default: dict | None = None,
    ) -> int:
        """Duplicate a record. Returns the new id."""
        return _odoo_copy_impl(model, id, default)

    @mcp.tool()
    def odoo_call_button(
        model: str,
        ids: list[int],
        method: str,
        kwargs: dict | None = None,
    ) -> Any:
        """Call an Odoo button method. Whitelisted to action_/button_/toggle_."""
        return _odoo_call_button_impl(model, ids, method, kwargs)

    @mcp.tool()
    def odoo_onchange(
        model: str,
        values: dict,
        trigger_field: str,
        view_id: int | None = None,
    ) -> dict:
        """Run Odoo's onchange for `trigger_field` against `values`.

        Auto-resolves field_onchange spec from the form view. Returns
        Odoo's response dict {value, warning?, domain?}.
        """
        return _odoo_onchange_impl(model, values, trigger_field, view_id)
