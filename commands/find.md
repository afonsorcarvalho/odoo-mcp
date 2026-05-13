---
description: Search a term across all text fields of an Odoo model
argument-hint: <model> <term>
---

# /odoo:find

Goal: locate records of `$ARGUMENTS` matching the given term in any text field, with minimal back-and-forth.

Steps:

1. Parse `$ARGUMENTS` as `<model> <term...>`. The first whitespace-separated token is the technical model name (e.g. `engc.os.relatorios`); the rest is the search term (may contain spaces). If the model name is missing or obviously wrong, ask the user to clarify before calling any tool.

2. Discover text fields of the model:

   ```
   mcp__plugin_odoo-mcp_odoo__odoo_fields_get
     model=<model>
     attributes=["string","type"]
     business_only=true
   ```

   Keep field names whose `type` is one of `char`, `text`, or `html`. Cap to a reasonable list (max ~12); if more, prefer ones whose `string` contains words like description, summary, name, problem, fault, observation, note, comment.

3. Run the multi-field search:

   ```
   mcp__plugin_odoo-mcp_odoo__odoo_multi_field_search
     model=<model>
     term=<term>
     fields=<list from step 2>
     read_fields=["id","name", "<1-2 most relevant text fields>"]
     limit=50
   ```

4. Present a compact markdown table: id, name, plus 1–2 columns showing the matching text (truncate each cell to ~120 chars). If zero hits, say so explicitly and list which fields were searched, so the user can refine.

5. Do NOT call write/create/unlink. This command is read-only.
