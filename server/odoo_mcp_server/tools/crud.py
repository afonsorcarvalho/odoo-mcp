"""Core CRUD + introspection MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import is_mixin_field


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_search(
        model: str,
        domain: list | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[int]:
        """Search records, return list of IDs.

        domain example: [["state", "=", "draft"], ["amount_total", ">", 100]]
        """
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if order:
            kwargs["order"] = order
        return transport.exec_kw(model, "search", [domain or []], kwargs)

    @mcp.tool()
    def odoo_search_count(model: str, domain: list | None = None) -> int:
        """Count records matching domain."""
        return transport.exec_kw(model, "search_count", [domain or []])

    @mcp.tool()
    def odoo_read(model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read records by IDs. fields=None reads all."""
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        return transport.exec_kw(model, "read", [ids], kwargs)

    @mcp.tool()
    def odoo_search_read(
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        """Search + read in one call. Most efficient for queries."""
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kwargs["fields"] = fields
        if order:
            kwargs["order"] = order
        return transport.exec_kw(model, "search_read", [domain or []], kwargs)

    @mcp.tool()
    def odoo_fields_get(
        model: str,
        attributes: list[str] | None = None,
        business_only: bool = False,
    ) -> dict:
        """Inspect model fields. Default attrs: string, type, required, readonly, help, selection, relation.

        business_only=True drops mail/activity/website/computed-counter mixin noise.
        """
        attrs = attributes or [
            "string", "type", "required", "readonly", "help", "selection", "relation",
        ]
        result = transport.exec_kw(model, "fields_get", [], {"attributes": attrs})
        if business_only:
            return {k: v for k, v in result.items() if not is_mixin_field(k)}
        return result

    @mcp.tool()
    def odoo_create(model: str, values: dict) -> int:
        """Create record. Returns new ID."""
        return transport.exec_kw(model, "create", [values])

    @mcp.tool()
    def odoo_write(model: str, ids: list[int], values: dict) -> bool:
        """Update records. Returns True on success."""
        return transport.exec_kw(model, "write", [ids, values])

    @mcp.tool()
    def odoo_unlink(model: str, ids: list[int]) -> bool:
        """Delete records. Returns True on success. Irreversible."""
        return transport.exec_kw(model, "unlink", [ids])

    @mcp.tool()
    def odoo_list_models(
        pattern: str | None = None,
        limit: int = 100,
        offset: int = 0,
        filter: str | None = None,
        filter_name: str | None = None,
    ) -> list[dict]:
        """List Odoo models matching technical name (ilike).

        Example: pattern="sale" returns models containing 'sale' (sale.order, sale.order.line, ...).
        `filter` and `filter_name` accepted as aliases for backwards compat.
        """
        pat = pattern or filter or filter_name
        domain: list = []
        if pat:
            domain = [["model", "ilike", pat]]
        return transport.exec_kw(
            "ir.model",
            "search_read",
            [domain],
            {
                "fields": ["model", "name", "modules"],
                "limit": limit,
                "offset": offset,
                "order": "model",
            },
        )

    @mcp.tool()
    def odoo_execute_kw(
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Generic escape hatch. Call any Odoo method via execute_kw."""
        return transport.exec_kw(model, method, args or [], kwargs or {})
