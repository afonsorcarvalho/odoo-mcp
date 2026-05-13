---
description: Switch active Odoo profile (multi-instance support)
allowed-tools:
  - mcp__plugin_odoo-mcp_odoo__odoo_list_profiles
  - mcp__plugin_odoo-mcp_odoo__odoo_use_profile
  - mcp__plugin_odoo-mcp_odoo__odoo_test_connection
  - AskUserQuestion
argument-hint: "[profile-name]"
---

Switch the active Odoo profile so subsequent MCP calls hit a different instance.

## Steps

1. If `$ARGUMENTS` contains a profile name, treat it as the target. Otherwise, call `odoo_list_profiles` and ask the user to pick one (use `AskUserQuestion`, options = profile names + url).
2. Call `mcp__plugin_odoo-mcp_odoo__odoo_use_profile(name=<chosen>)`.
3. Call `mcp__plugin_odoo-mcp_odoo__odoo_test_connection` to verify auth works against the new active profile.
4. Report: active profile name, url, db, user, and `ok` from test_connection.
