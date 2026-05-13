"""Search and discovery MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import strip_html


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_multi_field_search(
        model: str,
        term: str,
        fields: list[str],
        extra_domain: list | None = None,
        read_fields: list[str] | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        """Search a term across multiple text fields (OR), return search_read result.

        Builds: ['|', '|', ..., (f1, 'ilike', term), (f2, 'ilike', term), ...] AND extra_domain.
        `read_fields` controls returned record columns (None = all).
        """
        if not fields:
            raise ValueError("fields must contain at least one field name")
        or_clauses: list = list(["|"] * (len(fields) - 1))
        or_clauses.extend([(f, "ilike", term) for f in fields])
        domain: list = list(or_clauses)
        if extra_domain:
            domain = list(extra_domain) + domain
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if read_fields:
            kwargs["fields"] = read_fields
        if order:
            kwargs["order"] = order
        return transport.exec_kw(model, "search_read", [domain], kwargs)

    @mcp.tool()
    def odoo_resolve_xmlid(xmlid: str) -> dict:
        """Resolve external id (module.name) to {"model": str, "res_id": int}.

        Example: odoo_resolve_xmlid("base.user_admin") -> {"model": "res.users", "res_id": 2}
        """
        if "." not in xmlid:
            raise ValueError(f"xmlid must be in 'module.name' form, got {xmlid!r}")
        module, name = xmlid.split(".", 1)
        rows = transport.exec_kw(
            "ir.model.data",
            "search_read",
            [[["module", "=", module], ["name", "=", name]]],
            {"fields": ["model", "res_id"], "limit": 1},
        )
        if not rows:
            raise RuntimeError(f"xmlid not found: {xmlid}")
        r = rows[0]
        return {"model": r["model"], "res_id": r["res_id"]}

    @mcp.tool()
    def odoo_chatter_read(
        model: str,
        res_id: int,
        limit: int = 20,
        include_notifications: bool = True,
    ) -> list[dict]:
        """Read mail.message chatter for a record. Strips HTML from body.

        include_notifications=False returns only user comments.
        """
        types = ["comment", "notification"] if include_notifications else ["comment"]
        rows = transport.exec_kw(
            "mail.message",
            "search_read",
            [[["model", "=", model], ["res_id", "=", res_id], ["message_type", "in", types]]],
            {
                "fields": ["id", "date", "author_id", "subject", "body", "message_type", "subtype_id"],
                "limit": limit,
                "order": "date desc",
            },
        )
        for r in rows:
            r["body"] = strip_html(r.get("body"))
        return rows
