---
description: Configure an Odoo MCP profile (multi-instance, OS keyring storage)
allowed-tools:
  - mcp__plugin_odoo-mcp_odoo__odoo_add_profile
  - mcp__plugin_odoo-mcp_odoo__odoo_list_profiles
  - mcp__plugin_odoo-mcp_odoo__odoo_test_connection
  - AskUserQuestion
---

Configure a named Odoo profile so the MCP server can switch between multiple Odoo instances at runtime.

**Storage**
- Profile metadata (`url`, `db`, `user`, `name`): `~/.claude/odoo-mcp.profiles.json`
- Password: OS keyring (Windows Credential Manager / macOS Keychain / Linux libsecret).
  If keyring isn't available, falls back to `~/.claude/odoo-mcp.profiles.secrets.json` (chmod 600 on POSIX).

## Steps

### 1. Show current state

Call `mcp__plugin_odoo-mcp_odoo__odoo_list_profiles` to display existing profiles + active one + keyring availability. Never echo passwords.

### 2. Collect values

Ask the user for:

| Key | Required | Notes |
|-----|----------|-------|
| `name` | yes | Short identifier (e.g. `prod`, `staging`, `client-acme`). No leading underscore. |
| `url` | yes | Full URL with scheme. No trailing slash. |
| `db` | yes | Database name. |
| `user` | yes | Login (email or username). |
| `password` | yes | Password or API key. **Recommend API key.** |
| `activate` | no | Default true — make this the active profile after saving. |

Ask the user to paste values in `KEY=VALUE` format in a single message:

```
name=prod
url=https://my.odoo.com
db=my-database
user=user@example.com
password=...
```

### 3. Validate

- `url` starts with `http://` or `https://`.
- `name`, `url`, `db`, `user`, `password` non-empty.
- `name` does not start with `_` (reserved for `_env` / `_adhoc`).

Reject invalid input and ask again.

### 4. Save

Call `mcp__plugin_odoo-mcp_odoo__odoo_add_profile` with the collected values. Pass `activate=true` unless the user said otherwise.

### 5. Test

Call `mcp__plugin_odoo-mcp_odoo__odoo_test_connection` (no arg → tests active). Report `ok=true` with uid + version, or surface the error.

### 6. Confirm

Tell the user:
- Profile saved + active status.
- Where the metadata lives (`~/.claude/odoo-mcp.profiles.json`).
- Password storage backend (keyring vs fallback file) — pull from `odoo_list_profiles` keyring info.
- To add another instance, run `/odoo-mcp:setup` again with a different `name`.
- To switch instances later: `/odoo-mcp:use <name>` or call `odoo_use_profile`.

## Security rules

- Never echo `password` after collection. Mask in confirmations as `(set, length=N)`.
- Do not write the password to `TODO.md`, summaries, or any file other than via the MCP tool.
- If the user pastes the password in chat, do not repeat the literal value back.
