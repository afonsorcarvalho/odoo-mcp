---
description: Print a clean, business-only schema summary of an Odoo model
argument-hint: <model>
---

# /odoo:schema

Goal: render a quick-scan schema of `$ARGUMENTS` (a single Odoo technical model name like `sale.order` or `engc.os`) without mixin noise.

Steps:

1. Validate `$ARGUMENTS` is a single token (no spaces). If empty or has spaces, ask the user for the model name.

2. Fetch fields:

   ```
   mcp__plugin_odoo-mcp_odoo__odoo_fields_get
     model=<model>
     attributes=["string","type","relation","required","selection","help"]
     business_only=true
   ```

3. Render three markdown tables in this order. Each row: `field` | `string` | `type` | `relation/selection` | `required`.

   - **Required** — fields where `required` is true.
   - **Relations** — `type` in `many2one`, `one2many`, `many2many` (and not already shown as required). Show `relation` column.
   - **Other** — everything else. Group simple types together. For `selection` type, condense the selection options to `a|b|c` (truncate to ~40 chars).

4. Below the tables, list any field whose `help` is non-empty as a small "Notes" section: `- field: <help>` (one line each, max 8 entries).

5. Do NOT call write/create/unlink. Read-only.
