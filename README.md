# odoo-mcp

MCP server + Claude Code plugin for Odoo ERP via XML-RPC.

## Features

Exposes Odoo's `execute_kw` API as MCP tools:

| Tool | Purpose |
|------|---------|
| `odoo_list_profiles` | List configured Odoo instances + active one |
| `odoo_current_profile` | Return active profile (no password) + auth status |
| `odoo_add_profile` | Save a named profile (password → OS keyring), optionally activate |
| `odoo_use_profile` | Switch active profile at runtime |
| `odoo_remove_profile` | Delete a saved profile + its stored password |
| `odoo_connect_ad_hoc` | One-shot connection to an instance without persisting |
| `odoo_test_connection` | Authenticate against a profile without changing active |
| `odoo_authenticate` | Force re-auth of active profile, return uid + version |
| `odoo_search` | Search records, return IDs |
| `odoo_search_count` | Count matching records |
| `odoo_read` | Read records by ID |
| `odoo_search_read` | Search + read in one call |
| `odoo_fields_get` | Inspect model fields (introspection) |
| `odoo_create` | Create new record |
| `odoo_write` | Update records |
| `odoo_unlink` | Delete records |
| `odoo_list_models` | List available Odoo models (with pagination) |
| `odoo_multi_field_search` | OR-search a term across multiple text fields |
| `odoo_resolve_xmlid` | Resolve `module.name` external id to `{model, res_id}` |
| `odoo_chatter_read` | Read mail.message chatter for a record (HTML stripped) |
| `odoo_metadata` | Wrap `get_metadata` (xmlid, write_date, create_uid) |
| `odoo_view_get` | Inspect a view (parsed summary or raw arch) |
| `odoo_menu_tree` | Depth-bounded `ir.ui.menu` tree |
| `odoo_modules_list` | List `ir.module.module` (filter by state/pattern) |
| `odoo_access_check` | Check `read/write/create/unlink` rights for current user |
| `odoo_user_groups` | List groups for current uid |
| `odoo_company_list` | List companies the current user has access to |
| `odoo_call_button` | Call `action_*/button_*/toggle_*` methods (whitelisted) |
| `odoo_onchange` | Run onchange (auto-resolves spec from form view) |
| `odoo_default_get` | Return Odoo defaults for fields |
| `odoo_copy` | Duplicate a record |
| `odoo_execute_kw` | Generic escape hatch for any method |

## Slash commands

| Command | Purpose |
|---------|---------|
| `/odoo-mcp:setup` | Add a named Odoo profile (URL/DB/user/password → OS keyring) |
| `/odoo-mcp:profiles` | List all configured profiles + active one |
| `/odoo-mcp:use [name]` | Switch active profile at runtime |
| `/odoo-mcp:connect` | One-shot ad-hoc connection (not persisted) |
| `/odoo:find <model> <term>` | Search term across all text fields of a model |
| `/odoo:schema <model>` | Print clean business-only schema (skips mixin noise) |

## Requirements

- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/) (recommended) or pip
- Odoo instance with XML-RPC enabled (default for self-hosted and odoo.com)

## Install uv (Windows)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Configuration

The server connects to Odoo via **named profiles** — switch instances at runtime, no restart needed.

### Profiles

Stored in `~/.claude/odoo-mcp.profiles.json` (URL/db/user/name only — passwords never touch this file).

Passwords go into the OS keyring:

| OS | Backend |
|----|---------|
| Windows | Credential Manager (WinVault) |
| macOS | Keychain |
| Linux | Secret Service (libsecret) |

If the keyring is unavailable (e.g. headless Linux), the server falls back to `~/.claude/odoo-mcp.profiles.secrets.json` (chmod 600). Run `odoo_list_profiles` to see which backend is active.

### Quick setup

Inside Claude Code:

```
/odoo-mcp:setup
```

Asks for `name`, `url`, `db`, `user`, `password` and saves the profile. Repeat with a different `name` to add more Odoo instances.

Switch between them at any time:

```
/odoo-mcp:use prod
/odoo-mcp:use client-acme
```

Or programmatically: `odoo_use_profile(name="prod")`.

### One-shot connection

For a quick check against an instance you don't want to persist:

```
/odoo-mcp:connect
```

Sets a transient `_adhoc` profile, lost on server restart.

### Transport flag (XML-RPC vs JSON-RPC)

By default profiles use Odoo's XML-RPC endpoint (`/xmlrpc/2/`). Some Odoo instances
have server-side bugs that break XML-RPC authentication (e.g. the `website` module
`AttributeError: 'Request' object has no attribute 'session'`). For those instances,
set `transport="jsonrpc"` when adding the profile — the server will POST to `/jsonrpc`
instead, which bypasses the buggy code path:

```
odoo_add_profile(name="myprod", url="https://my.odoo.com", db="mydb",
                 user="me@example.com", password="...", transport_flag="jsonrpc")
```

Or via Python one-liner:
```bash
uv run python -c "
from odoo_mcp_server import profiles
profiles.set_profile('myprod', 'https://my.odoo.com', 'mydb', 'me@example.com',
                     password=None, transport='jsonrpc')
"
```

Valid values: `"xmlrpc"` (default, back-compat), `"jsonrpc"`.
Uses stdlib `urllib.request` — no new dependencies.

### Backwards compatibility (legacy env vars)

The older env-var path still works as a fallback profile named `_env`. If `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD` are all set in the environment (e.g. via `.mcp.json` or `~/.claude/odoo-mcp.env`), the server uses them when no other profile is active.

| Var | Example | Notes |
|-----|---------|-------|
| `ODOO_URL` | `https://my.odoo.com` | No trailing slash |
| `ODOO_DB` | `my-database` | Database name |
| `ODOO_USER` | `user@example.com` | Login |
| `ODOO_PASSWORD` | `secret-or-api-key` | Password or API key (preferred) |
| `ODOO_TIMEOUT` | `30` | Optional. XML-RPC socket timeout in seconds (default 30) |
| `ODOO_LOG_LEVEL` | `INFO` | Optional. `DEBUG`, `INFO`, `WARNING`, `ERROR` (default INFO) |

API keys: in Odoo go to `Settings → Users → Account Security → New API Key`.

Logs go to **stderr** (stdout is reserved for the MCP protocol). The server retries transient network errors (3 attempts, exponential backoff) and re-authenticates automatically on stale UID.

## Use as Claude Code plugin

This repo is a Claude Code plugin. From Claude Code:

```
/plugin marketplace add <path-to-this-repo>
/plugin install odoo-mcp
```

Then run `/odoo-mcp:setup` to configure credentials. Restart Claude Code. Verify with `/mcp` — should show `odoo` connected.

## Use standalone (any MCP client)

```bash
cd server
uv sync
ODOO_URL=... ODOO_DB=... ODOO_USER=... ODOO_PASSWORD=... uv run odoo-mcp
```

Or with pip:

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
python -m odoo_mcp_server
```

## Examples

Once connected, ask Claude things like:

- "List all sale orders in draft state"
  → `odoo_search_read("sale.order", [["state","=","draft"]], ["name","partner_id","amount_total"])`

- "What fields does res.partner have?"
  → `odoo_fields_get("res.partner")`

- "Create a partner named ACME"
  → `odoo_create("res.partner", {"name": "ACME", "is_company": true})`

- "Mark order 42 as confirmed"
  → `odoo_execute_kw("sale.order", "action_confirm", [[42]])`

## Domain syntax (Odoo)

```python
[]                                          # all
[["state", "=", "draft"]]                   # equality
[["amount_total", ">", 1000]]               # comparison
["|", ["a","=",1], ["b","=",2]]             # OR
[["name", "ilike", "acme"]]                 # case-insensitive substring
[["partner_id.country_id.code", "=", "PT"]] # dotted (search through M2O)
```

## Security

- Server uses authenticated XML-RPC. Uses cached uid after first call.
- Credentials never leave your machine — server runs locally as stdio child process.
- `odoo_unlink` is irreversible — confirm before calling on production data.
- Use an API key over a password.
- Restrict the Odoo user's access rights to least privilege.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Odoo authentication failed` | Wrong db/user/password, or 2FA blocking — use API key |
| `ConnectionRefusedError` | XML-RPC disabled, or wrong URL |
| `Object xmlrpc:... does not exist` | Wrong model name, check with `odoo_list_models` |
| Server doesn't appear in `/mcp` | Run `claude --debug`, check uv installed, check env vars |
