# Phase 1 — Foundation Tools Design

**Date:** 2026-05-09
**Status:** Design approved, awaiting implementation plan
**Scope:** Add 11 inspection + workflow MCP tools, refactor server into per-domain modules

## Context

The `odoo-mcp` plugin currently exposes 20 MCP tools and 6 slash commands, all
defined inline in `server/odoo_mcp_server/server.py` (552 LOC). To grow without
that file becoming unmaintainable, this phase splits the server into per-domain
modules and adds 11 new "foundation" tools covering workflow execution and model
inspection.

This is **Phase 1 of 5**:

- **Phase 1 (this spec)** — Foundation tools (workflow + inspection)
- Phase 2 — Content/comms (attachments, chatter_post, report_render)
- Phase 3 — Bulk/export (export, import via load(), batching, browse_url)
- Phase 4 — Discovery UX (slash commands `explain`/`menu`/`perm`, TTL cache, schema with relations)
- Phase 5 — Subagents + skills (`odoo-analyst` read-only, `odoo-debugger`, `odoo-domain`, `odoo-recipes`)

Each phase will have its own spec, plan, and implementation cycle.

## Goals

1. Add 11 foundation tools usable across future phases.
2. Refactor server into per-domain modules to support continued growth.
3. Preserve existing tool names and behavior — no breaking changes for clients.

## Non-goals

- TTL cache for `fields_get` / `view_get` — deferred to Phase 4.
- Multi-company switching (`force_company` context injection) — deferred.
- `ODOO_READ_ONLY` flag, `unlink` dry-run, audit log — deferred to a separate
  safety-focused phase already on `TODO.md`.
- Confirm gates / hooks for destructive `call_button` calls — deferred.

## File layout

```
server/odoo_mcp_server/
├── __init__.py
├── server.py              # FastMCP setup + main(); registers tool modules
├── profiles.py            # unchanged
├── transport.py           # NEW: _TimeoutTransport, _proxy, _connect, _exec,
│                          #      _active_creds, _invalidate_active,
│                          #      _is_session_fault, load_env_file, _timeout
├── _helpers.py            # NEW: strip_html, is_mixin_field, parse_view_arch,
│                          #      is_button_method, BUTTON_PREFIXES,
│                          #      safe_context_merge
└── tools/
    ├── __init__.py
    ├── auth.py            # NEW: profile + auth tools (8 existing)
    │                      #      odoo_list_profiles, odoo_current_profile,
    │                      #      odoo_add_profile, odoo_use_profile,
    │                      #      odoo_remove_profile, odoo_connect_ad_hoc,
    │                      #      odoo_test_connection, odoo_authenticate
    ├── crud.py            # NEW: search/read/write/create/unlink/fields_get/
    │                      #      list_models/execute_kw/search_count/search_read
    ├── discovery.py       # NEW: multi_field_search, resolve_xmlid, chatter_read
    ├── inspection.py      # NEW (Phase 1): view_get, menu_tree, modules_list,
    │                      #               access_check, user_groups,
    │                      #               metadata, company_list
    └── workflow.py        # NEW (Phase 1): call_button, onchange,
                           #               default_get, copy
```

`server.py` shrinks to ~30 LOC: imports, `FastMCP("odoo")`, `main()` calling
each module's `register(mcp)` and `mcp.run()`.

Each `tools/*.py` exports a single `register(mcp: FastMCP) -> None` that wraps
its functions with `@mcp.tool()`. Tools call `transport._exec(...)` directly.

`_helpers.py` is pure (no transport/profile imports) so helpers are unit-testable
in isolation.

## Design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `call_button` safety | Whitelist prefixes `action_/button_/toggle_*` + return action verbatim | Reject obvious mistakes; defer confirm gates to safety phase |
| `onchange` API | Auto-resolve `field_onchange` spec from default form view | Easier for callers; one extra round-trip acceptable |
| `view_get` output | Parsed summary by default, `raw=True` for full arch + fields | Compact for LLM consumption; raw available when needed |
| Multi-company | List only (`company_list`); no switch tool | Caller passes `context` manually if needed; minimum scope |
| TTL cache | Defer to Phase 4 | Keeps Phase 1 strictly tools |
| Architecture | Split by domain (option B) | Enables sustained growth across all 5 phases |

## Tool API contracts

### `inspection.py`

#### `odoo_metadata(model: str, ids: list[int]) -> list[dict]`

Wraps Odoo `get_metadata`. Returns
`[{id, xmlid, noupdate, create_uid, create_date, write_uid, write_date}, ...]`
for each id. Errors for invalid model are propagated as MCP errors with the
model name.

#### `odoo_view_get(model: str, view_type: str = "form", view_id: int | None = None, raw: bool = False) -> dict`

Wraps `fields_view_get(view_id, view_type)`.

- `view_id=None` → Odoo picks default view for `view_type` (existing
  `fields_view_get` behavior; no extra logic on our side).
- Default output: `{model, view_type, view_id, name, fields_summary: [...]}`
  where `fields_summary` is the result of `parse_view_arch` — a flat list of
  `{name, widget?, readonly?, required?, invisible?, string?}` for each field
  visible in the view, with wrapper tags (`sheet`, `group`, `notebook`, `page`)
  dropped.
- `raw=True`: adds `arch` (XML string) and `fields` (full Odoo dict).
- `view_type` ∈ `("form", "tree", "kanban", "search", "calendar", "pivot", "graph")`.

#### `odoo_menu_tree(depth: int = 3, active_only: bool = True) -> list[dict]`

Builds a tree from `ir.ui.menu`. Starts at roots (`parent_id=False`), recurses
via `child_id`, trimmed at `depth`.

- Returns `[{id, name, sequence, action?, children: [...]}, ...]`.
- `active_only=True` adds `[("active","=",True)]` to all reads — hides menus
  the current user cannot see (Odoo's standard behavior). Menus belonging to
  uninstalled modules don't exist in `ir.ui.menu`, so no separate filter is
  needed.

#### `odoo_modules_list(state: str = "installed", pattern: str | None = None) -> list[dict]`

`ir.module.module.search_read` with `[("state","=",state)]` and optionally
`[("name","ilike",pattern)]`.

- Fields returned: `["name", "shortdesc", "state", "installed_version"]`.
- `state` ∈ `("installed", "uninstalled", "to install", "to upgrade", "to remove", "all")`.
- `state="all"` skips the state filter.

#### `odoo_access_check(model: str, operation: str = "read", raise_exception: bool = False) -> dict`

Calls `check_access_rights(operation, raise_exception=False)` via execute_kw.

- `operation` ∈ `("read", "write", "create", "unlink")`.
- Returns `{model, operation, allowed: bool}`.
- `raise_exception=True` propagates Odoo `AccessError` as an MCP error.

#### `odoo_user_groups(uid: int | None = None) -> dict`

Defaults `uid` to the current authenticated user.

- Reads `res.users.groups_id` for that uid; reads each group's `full_name` and
  `category_id.name`.
- Returns `{uid, login, groups: [{id, name, full_name, category}]}`.

#### `odoo_company_list() -> list[dict]`

Reads `res.users.company_ids` for the current uid; for each company reads
`name, currency_id, parent_id`.

- Returns `[{id, name, currency_id, parent_id?}, ...]`.

### `workflow.py`

#### `odoo_call_button(model: str, ids: list[int], method: str, kwargs: dict | None = None) -> Any`

Validates `is_button_method(method)` (must start with `action_`, `button_`, or
`toggle_`). Rejects with a clear MCP error otherwise.

- Calls `_exec(model, method, [ids], kwargs or {})`.
- Returns the value verbatim — typically `True`, an `ir.actions.*` dict, or
  `False`.

#### `odoo_onchange(model: str, values: dict, trigger_field: str, view_id: int | None = None) -> dict`

- Internally calls `fields_view_get(view_id, "form")` to extract the
  `field_onchange` spec (a dict mapping field → on-change spec string).
- Calls `model.onchange([], values, trigger_field, field_onchange_spec)`.
- Returns `{value: {...}, warning?: {...}, domain?: {...}}`.

#### `odoo_default_get(model: str, fields: list[str] | None = None) -> dict`

`fields=None` → uses keys from `fields_get` (all fields).

- Wraps `default_get(fields)`.
- Returns dict `{field: value}`.

#### `odoo_copy(model: str, id: int, default: dict | None = None) -> int`

Wraps `copy(id, default or {})`.

- Returns the new record id.

## Helpers (`_helpers.py`)

```python
BUTTON_PREFIXES = ("action_", "button_", "toggle_")

def is_button_method(name: str) -> bool:
    return name.startswith(BUTTON_PREFIXES)

def parse_view_arch(arch_xml: str) -> list[dict]:
    """Tree-shake arch XML → flat list of visible fields:
    [{name, widget?, readonly?, required?, invisible?, string?}, ...]
    Drops <sheet>/<group>/<notebook>/<page> wrappers.
    Uses xml.etree.ElementTree."""

def safe_context_merge(base: dict | None, extra: dict | None) -> dict:
    """Merge two contexts; extra wins. Both args may be None."""

# moved from server.py:
def strip_html(s: str | None) -> str: ...
def is_mixin_field(name: str) -> bool: ...
```

Pure functions — no imports of `transport` or `profiles`. Unit-testable in isolation.

## `server.py` after refactor

```python
from mcp.server.fastmcp import FastMCP
from . import profiles, transport
from .tools import auth, crud, discovery, inspection, workflow

mcp = FastMCP("odoo")

def main() -> None:
    transport.load_env_file()
    auth.register(mcp)
    crud.register(mcp)
    discovery.register(mcp)
    inspection.register(mcp)
    workflow.register(mcp)
    mcp.run()
```

Each `tools/*.py`:

```python
from ..transport import _exec
# ...

def register(mcp):
    @mcp.tool()
    def odoo_view_get(model: str, view_type: str = "form",
                      view_id: int | None = None, raw: bool = False) -> dict:
        ...
```

## Testing

New `server/tests/` directory.

### `test_helpers.py` — pure unit tests

- `parse_view_arch` against fixture XML (form with sheet/group/notebook).
- `is_button_method` boundaries (`action_x` ✓, `_action_x` ✗, `actionx` ✗).
- `safe_context_merge` with `(None, None)`, `(dict, None)`, `(None, dict)`,
  overlapping keys.

### `test_smoke_phase1.py` — integration

Targeted at the local Odoo 16 instance already used by the existing 11/11 smoke
test (db `odoo-steriliza`).

- `view_get("res.partner", "form")` → `fields_summary` non-empty
- `menu_tree(depth=2)` → tree contains `Settings` / `Contacts`
- `modules_list("installed")` → contains `base`
- `access_check("res.partner", "read")` → `allowed=True`
- `user_groups()` → contains a `Settings` or admin group
- `company_list()` → length ≥ 1
- `metadata("res.partner", [admin_partner_id])` → xmlid resolves
- `default_get("res.partner")` → returns dict
- `copy("res.partner", id)` → new id; cleanup with `unlink`
- `call_button("sale.order", [draft_id], "action_confirm")` — optional, skipped
  if no draft sale order exists
- `onchange("res.partner", {"company_type": "company"}, "company_type")` → dict

Use `pytest` with marker `@pytest.mark.integration` so integration tests can be
skipped without Odoo (`uv run pytest -m "not integration"` for unit only).

The pre-existing 11/11 smoke test against the same db must continue to pass
unchanged after the refactor — this is the regression gate.

## Migration / breaking changes

- All existing tool names and signatures preserved → MCP clients are unaffected.
- `server.py` public API (`main`) preserved → entry point `odoo-mcp` works.
- Internal imports change but nothing external imports from this package.

Risks:

- **FastMCP decorator timing**: tools currently registered at import time via
  `@mcp.tool()` at module level. After refactor they register inside
  `register(mcp)` called from `main()`. This is supported by FastMCP and is
  cleaner. Verified no other code relies on import-time registration.
- **`_exec` shared state**: `_invalidate_active`, `_active_creds`, and the auth
  cache move to `transport.py` intact. The `profiles` module is unchanged.
- **Refactor scope**: this PR moves ~500 LOC and adds ~400 new LOC. It must be
  one atomic change so that the smoke test runs against the final state.

## Out of scope (deferred)

- TTL cache for introspection (Phase 4)
- Confirm gates / hooks for destructive tools (safety phase)
- `ODOO_READ_ONLY` flag (safety phase)
- Multi-company switch tool (`set_company`) — only `company_list` in Phase 1
- Phases 2-5 (own specs)
