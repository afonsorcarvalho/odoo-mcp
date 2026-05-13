"""Odoo MCP server. Exposes XML-RPC operations as MCP tools.

Multi-profile capable: switch between Odoo instances at runtime via
`odoo_use_profile` / `odoo_add_profile` / `odoo_connect_ad_hoc`.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import transport
from .tools import auth, crud, discovery, inspection, workflow

transport.load_env_file()

mcp = FastMCP("odoo-mcp")
auth.register(mcp)
crud.register(mcp)
discovery.register(mcp)
inspection.register(mcp)
workflow.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
