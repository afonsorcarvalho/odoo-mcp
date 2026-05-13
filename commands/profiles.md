---
description: List configured Odoo profiles and show active one
allowed-tools:
  - mcp__plugin_odoo-mcp_odoo__odoo_list_profiles
  - mcp__plugin_odoo-mcp_odoo__odoo_current_profile
---

List all configured Odoo profiles.

## Steps

1. Call `mcp__plugin_odoo-mcp_odoo__odoo_list_profiles`.
2. Render as a table: name, url, db, user, active marker, transient marker (for `_env` / `_adhoc`).
3. Show keyring backend status (`keyring_available` true/false).
4. If no profiles exist, suggest running `/odoo-mcp:setup`.
