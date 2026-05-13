---
description: Connect to an Odoo instance ad-hoc (no persistence) for the current session
allowed-tools:
  - mcp__plugin_odoo-mcp_odoo__odoo_connect_ad_hoc
  - AskUserQuestion
---

One-shot connection to an Odoo instance without saving credentials. Useful for quick checks against a sandbox or a customer's instance you don't want to persist.

The connection is lost when the MCP server restarts. Use `/odoo-mcp:setup` to persist instead.

## Steps

1. Ask the user for `url`, `db`, `user`, `password` (single message, `KEY=VALUE` per line).
2. Validate: url starts with http(s)://, others non-empty.
3. Call `mcp__plugin_odoo-mcp_odoo__odoo_connect_ad_hoc` with the values.
4. Report uid + version. If failure, surface error.

## Security

- Never echo `password` back to the user.
- Do not write to any file. The MCP tool keeps the credentials in process memory only.
