# Phase 1 Foundation Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `odoo-mcp` server into per-domain modules and add 11 new foundation tools (workflow + inspection) without changing behavior of existing tools.

**Architecture:** Split `server.py` into `transport.py` (XML-RPC plumbing), `_helpers.py` (pure helpers), and `tools/{auth,crud,discovery,inspection,workflow}.py` (one `register(mcp)` per module). New tools are thin wrappers over `transport._exec`.

**Tech Stack:** Python ≥3.10, FastMCP (`mcp[cli]>=1.2.0`), `xmlrpc.client`, `keyring`, `pytest` (new).

**Spec:** `docs/superpowers/specs/2026-05-09-phase1-foundation-tools-design.md`

---

## Notes for the implementer

- Working directory throughout: `c:/Users/Afonso/OneDrive/Documentos/Development/odoo_mcp/server`. All `pytest` / `uv` commands run from there unless noted.
- Tests live under `server/tests/`. Use the marker `@pytest.mark.integration` for tests that need a live Odoo instance.
- The integration smoke target is the local Odoo 16 instance already used by the historical 11/11 smoke (db `odoo-steriliza`). Credentials come from the active profile or `~/.claude/odoo-mcp.env`.
- Commit after every task. Conventional Commits: `feat:`, `refactor:`, `test:`, `chore:`.
- DRY, YAGNI, TDD. Don't add fields, parameters, or branches the spec doesn't require.

---

## Task 1: Add pytest, create tests/ scaffold, write a smoke unit test

**Files:**
- Modify: `server/pyproject.toml`
- Create: `server/tests/__init__.py`
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_smoke.py`

- [ ] **Step 1: Add pytest as dev dep**

Edit `server/pyproject.toml` — add an `[dependency-groups]` block (PEP 735, supported by uv):

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

And add the integration marker registration:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: hits a live Odoo server (skipped by default in CI)",
]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
"""Pytest config. Skips integration tests unless ODOO_TEST_LIVE=1."""
from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("ODOO_TEST_LIVE") == "1":
        return
    skip_integration = pytest.mark.skip(reason="set ODOO_TEST_LIVE=1 to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
```

- [ ] **Step 4: Create `tests/test_smoke.py` with one passing test**

```python
def test_pytest_runs():
    assert True
```

- [ ] **Step 5: Sync deps and run**

```bash
uv sync --group dev
uv run pytest -v
```

Expected: 1 passed in <1s.

- [ ] **Step 6: Commit**

```bash
git add server/pyproject.toml server/tests/__init__.py server/tests/conftest.py server/tests/test_smoke.py server/uv.lock
git commit -m "chore: add pytest dev dep and tests/ scaffold"
```

---

## Task 2: Create `_helpers.py` with `is_button_method` (TDD)

**Files:**
- Create: `server/tests/test_helpers.py`
- Create: `server/odoo_mcp_server/_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_helpers.py`:

```python
from odoo_mcp_server._helpers import is_button_method


def test_is_button_method_action_prefix():
    assert is_button_method("action_confirm") is True


def test_is_button_method_button_prefix():
    assert is_button_method("button_validate") is True


def test_is_button_method_toggle_prefix():
    assert is_button_method("toggle_active") is True


def test_is_button_method_rejects_no_prefix():
    assert is_button_method("write") is False


def test_is_button_method_rejects_underscore_action():
    assert is_button_method("_action_confirm") is False


def test_is_button_method_rejects_actionx():
    assert is_button_method("actionx") is False
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: ImportError / collection failure (`_helpers` module missing).

- [ ] **Step 3: Create `_helpers.py` with minimal impl**

```python
"""Pure helpers — no transport / profile imports."""
from __future__ import annotations

BUTTON_PREFIXES = ("action_", "button_", "toggle_")


def is_button_method(name: str) -> bool:
    """True iff `name` starts with one of BUTTON_PREFIXES."""
    return name.startswith(BUTTON_PREFIXES)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/_helpers.py server/tests/test_helpers.py
git commit -m "feat(_helpers): add is_button_method whitelist"
```

---

## Task 3: Add `safe_context_merge` to `_helpers.py` (TDD)

**Files:**
- Modify: `server/tests/test_helpers.py`
- Modify: `server/odoo_mcp_server/_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `server/tests/test_helpers.py`:

```python
from odoo_mcp_server._helpers import safe_context_merge


def test_safe_context_merge_both_none():
    assert safe_context_merge(None, None) == {}


def test_safe_context_merge_base_only():
    assert safe_context_merge({"lang": "pt_PT"}, None) == {"lang": "pt_PT"}


def test_safe_context_merge_extra_only():
    assert safe_context_merge(None, {"tz": "UTC"}) == {"tz": "UTC"}


def test_safe_context_merge_extra_wins():
    out = safe_context_merge({"lang": "en_US"}, {"lang": "pt_PT", "tz": "UTC"})
    assert out == {"lang": "pt_PT", "tz": "UTC"}


def test_safe_context_merge_does_not_mutate_inputs():
    base = {"lang": "en_US"}
    extra = {"tz": "UTC"}
    safe_context_merge(base, extra)
    assert base == {"lang": "en_US"}
    assert extra == {"tz": "UTC"}
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: 5 new tests fail with ImportError.

- [ ] **Step 3: Implement**

Append to `_helpers.py`:

```python
def safe_context_merge(base: dict | None, extra: dict | None) -> dict:
    """Merge two contexts; extra wins. None-safe. Returns a new dict."""
    out: dict = {}
    if base:
        out.update(base)
    if extra:
        out.update(extra)
    return out
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/_helpers.py server/tests/test_helpers.py
git commit -m "feat(_helpers): add safe_context_merge"
```

---

## Task 4: Add `parse_view_arch` to `_helpers.py` (TDD)

**Files:**
- Modify: `server/tests/test_helpers.py`
- Modify: `server/odoo_mcp_server/_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_helpers.py`:

```python
from odoo_mcp_server._helpers import parse_view_arch


def test_parse_view_arch_form_with_sheet_group():
    arch = """
    <form>
      <sheet>
        <group>
          <field name="name" required="1"/>
          <field name="email" widget="email"/>
        </group>
        <notebook>
          <page string="Other">
            <field name="phone" readonly="1"/>
          </page>
        </notebook>
      </sheet>
    </form>
    """
    out = parse_view_arch(arch)
    names = [f["name"] for f in out]
    assert names == ["name", "email", "phone"]
    by_name = {f["name"]: f for f in out}
    assert by_name["name"]["required"] == "1"
    assert by_name["email"]["widget"] == "email"
    assert by_name["phone"]["readonly"] == "1"


def test_parse_view_arch_tree():
    arch = '<tree><field name="display_name"/><field name="state"/></tree>'
    out = parse_view_arch(arch)
    assert [f["name"] for f in out] == ["display_name", "state"]


def test_parse_view_arch_skips_non_field_tags():
    arch = """
    <form>
      <header><button name="action_x"/></header>
      <field name="name"/>
    </form>
    """
    out = parse_view_arch(arch)
    assert [f["name"] for f in out] == ["name"]


def test_parse_view_arch_invalid_xml_returns_empty():
    assert parse_view_arch("<not closed") == []
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: 4 new tests fail with ImportError.

- [ ] **Step 3: Implement**

Append to `_helpers.py`:

```python
import xml.etree.ElementTree as _ET

# Attributes captured per <field> in parse_view_arch.
_FIELD_ATTRS = ("widget", "readonly", "required", "invisible", "string")


def parse_view_arch(arch_xml: str) -> list[dict]:
    """Tree-shake an Odoo view arch XML into a flat list of fields.

    Returns: [{"name": str, **{attr: str for attr in _FIELD_ATTRS if present}}, ...]
    Wrapper tags (sheet/group/notebook/page/header/etc.) are descended into;
    only <field> elements end up in the output. Returns [] on parse error.
    """
    try:
        root = _ET.fromstring(arch_xml)
    except _ET.ParseError:
        return []
    out: list[dict] = []
    for field in root.iter("field"):
        name = field.get("name")
        if not name:
            continue
        entry: dict = {"name": name}
        for attr in _FIELD_ATTRS:
            v = field.get(attr)
            if v is not None:
                entry[attr] = v
        out.append(entry)
    return out
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/test_helpers.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/_helpers.py server/tests/test_helpers.py
git commit -m "feat(_helpers): add parse_view_arch"
```

---

## Task 5: Move `strip_html` and `is_mixin_field` from `server.py` to `_helpers.py`

**Files:**
- Modify: `server/odoo_mcp_server/_helpers.py`
- Modify: `server/odoo_mcp_server/server.py`
- Modify: `server/tests/test_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_helpers.py`:

```python
from odoo_mcp_server._helpers import is_mixin_field, strip_html


def test_strip_html_basic():
    assert strip_html("<p>hello <b>world</b></p>") == "hello world"


def test_strip_html_collapses_whitespace():
    assert strip_html("<p>a</p>\n\n<p>b</p>") == "a b"


def test_strip_html_none_or_empty():
    assert strip_html(None) == ""
    assert strip_html("") == ""


def test_is_mixin_field_message():
    assert is_mixin_field("message_follower_ids") is True


def test_is_mixin_field_count_suffix():
    assert is_mixin_field("activity_count") is True


def test_is_mixin_field_business_field():
    assert is_mixin_field("partner_id") is False
    assert is_mixin_field("name") is False
```

- [ ] **Step 2: Move impl to `_helpers.py`**

Append to `_helpers.py`:

```python
import re as _re

_HTML_TAG = _re.compile(r"<[^>]+>")
_WS = _re.compile(r"\s+")

_MIXIN_PATTERNS = [
    _re.compile(r"^activity_"),
    _re.compile(r"^message_"),
    _re.compile(r"^website_message_"),
    _re.compile(r"^has_message$"),
    _re.compile(r"^my_activity_"),
    _re.compile(r"_count$"),
    _re.compile(r"^__last_update$"),
    _re.compile(r"^display_name$"),
]


def strip_html(s: str | None) -> str:
    """Strip HTML tags and collapse whitespace. None/empty → ""."""
    if not s:
        return ""
    return _WS.sub(" ", _HTML_TAG.sub(" ", s)).strip()


def is_mixin_field(name: str) -> bool:
    """True for activity/message/website mixin / counter / metadata fields."""
    return any(p.search(name) for p in _MIXIN_PATTERNS)
```

- [ ] **Step 3: Update `server.py` to import from `_helpers`**

In `server.py`:

- Delete the local `_HTML_TAG`, `_WS`, `_MIXIN_PATTERNS`, `_strip_html`, `_is_mixin_field`.
- At the top of the file, add: `from ._helpers import is_mixin_field as _is_mixin_field, strip_html as _strip_html`.

(Aliasing as `_is_mixin_field` / `_strip_html` keeps the existing call sites unchanged.)

- [ ] **Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: all helper tests pass; no regressions.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/_helpers.py server/odoo_mcp_server/server.py server/tests/test_helpers.py
git commit -m "refactor: move strip_html and is_mixin_field to _helpers"
```

---

## Task 6: Extract `transport.py` from `server.py`

**Files:**
- Create: `server/odoo_mcp_server/transport.py`
- Modify: `server/odoo_mcp_server/server.py`

- [ ] **Step 1: Create `transport.py`**

Move these symbols from `server.py` to `transport.py` (verbatim):

- `_load_env_file` → renamed to `load_env_file` (public)
- `_timeout`, `_TimeoutTransport`, `_state`, `_TRANSIENT`
- `_active_creds`, `_proxy`, `_connect`, `_is_session_fault`, `_invalidate_active`, `_exec`
- The module-level `logging.basicConfig(...)` block and `log` logger

`transport.py`:

```python
"""XML-RPC transport, auth caching, and retry logic.

Pure infrastructure — no MCP tool decorators here. Tools live under tools/*.
"""
from __future__ import annotations

import http.client
import logging
import os
import socket
import sys
import time
import xmlrpc.client
from typing import Any

from . import profiles

logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("ODOO_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s odoo-mcp %(message)s",
)
log = logging.getLogger("odoo-mcp")


def load_env_file() -> None:
    """Load `~/.claude/odoo-mcp.env` into os.environ for keys not already set."""
    path = os.path.join(os.path.expanduser("~"), ".claude", "odoo-mcp.env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                k = k.strip()
                v = v.strip()
                if k and not os.environ.get(k):
                    os.environ[k] = v
    except Exception as e:
        log.warning("failed loading env file %s: %s", path, e)


def _timeout() -> float:
    try:
        return float(os.environ.get("ODOO_TIMEOUT", "30"))
    except ValueError:
        return 30.0


class _TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: float, use_https: bool):
        super().__init__()
        self._timeout = timeout
        self._use_https = use_https

    def make_connection(self, host):
        if self._connection and host == self._connection[0]:
            return self._connection[1]
        chost, self._extra_headers, _x509 = self.get_host_info(host)
        if self._use_https:
            self._connection = host, http.client.HTTPSConnection(chost, timeout=self._timeout)
        else:
            self._connection = host, http.client.HTTPConnection(chost, timeout=self._timeout)
        return self._connection[1]


_state: dict[str, dict[str, Any]] = {}

_TRANSIENT = (
    xmlrpc.client.ProtocolError,
    ConnectionError,
    socket.timeout,
    OSError,
)


def _active_creds() -> tuple[str, str, str, str, str]:
    name = profiles.current_profile_name()
    if not name:
        raise RuntimeError(
            "No active Odoo profile. Use `odoo_add_profile` to create one, "
            "or `odoo_connect_ad_hoc` for a one-shot connection."
        )
    p = profiles.get_profile(name)
    if not p:
        raise RuntimeError(f"active profile '{name}' has no resolvable credentials")
    return name, p["url"], p["db"], p["user"], p["password"]


def proxy(url_base: str, path: str) -> xmlrpc.client.ServerProxy:
    full = f"{url_base.rstrip('/')}{path}"
    transport = _TimeoutTransport(_timeout(), use_https=full.startswith("https://"))
    return xmlrpc.client.ServerProxy(full, allow_none=True, transport=transport)


def connect() -> tuple[int, xmlrpc.client.ServerProxy, str, str]:
    name, url, db, user, password = _active_creds()
    cache = _state.get(name)
    if cache is None:
        log.info("authenticating profile=%s db=%s user=%s url=%s", name, db, user, url)
        common = proxy(url, "/xmlrpc/2/common")
        uid = common.authenticate(db, user, password, {})
        if not uid:
            raise RuntimeError(
                f"Odoo authentication failed for profile={name} user={user} db={db}. "
                "Check credentials and url."
            )
        log.info("authenticated profile=%s uid=%d", name, uid)
        cache = {"uid": uid, "models": proxy(url, "/xmlrpc/2/object")}
        _state[name] = cache
    return cache["uid"], cache["models"], db, password


def _is_session_fault(exc: xmlrpc.client.Fault) -> bool:
    msg = (exc.faultString or "").lower()
    return any(s in msg for s in ("accessdenied", "session expired", "sessionexpired"))


def invalidate_active() -> None:
    name = profiles.current_profile_name()
    if name and name in _state:
        del _state[name]


def exec_kw(model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
    """Execute Odoo method with retry on transient errors and re-auth on stale UID."""
    last_exc: Exception | None = None
    reauthed = False
    for attempt in range(3):
        start = time.monotonic()
        try:
            uid, models, db, password = connect()
            result = models.execute_kw(db, uid, password, model, method, args, kwargs or {})
            log.debug(
                "exec model=%s method=%s args=%d ok dur=%.0fms",
                model, method, len(args), (time.monotonic() - start) * 1000,
            )
            return result
        except xmlrpc.client.Fault as e:
            if not reauthed and _is_session_fault(e):
                log.warning("stale session, re-authenticating: %s", e.faultString)
                invalidate_active()
                reauthed = True
                continue
            log.error("Odoo fault model=%s method=%s: %s", model, method, e.faultString)
            raise
        except _TRANSIENT as e:
            last_exc = e
            log.warning(
                "transient error model=%s method=%s attempt=%d: %s",
                model, method, attempt + 1, e,
            )
            time.sleep(0.5 * (2 ** attempt))
            invalidate_active()
    assert last_exc is not None
    raise last_exc
```

(Names are deliberately exposed without leading underscore where they're now consumed across modules: `proxy`, `connect`, `exec_kw`, `invalidate_active`, `load_env_file`. `_state`, `_active_creds`, `_TRANSIENT`, `_TimeoutTransport`, `_timeout`, `_is_session_fault` stay private.)

- [ ] **Step 2: Update `server.py` to import from `transport`**

In `server.py`:

- Delete every symbol that was moved.
- At the top: `from . import transport`. Change `_load_env_file()` call → `transport.load_env_file()`. Replace `_state` references with `transport._state`, `_invalidate_active()` with `transport.invalidate_active()`, `_proxy(...)` with `transport.proxy(...)`, `_connect()` with `transport.connect()`, `_exec(...)` with `transport.exec_kw(...)`, `_active_creds()` with `transport._active_creds()`.
- Remove the now-unused `import http.client`, `import socket`, `import time`, `import xmlrpc.client`, `import logging`, `import sys` — only keep imports `server.py` still needs.

After this step, `server.py` still defines all 20 tools but delegates plumbing to `transport`.

- [ ] **Step 3: Smoke-run the server import**

```bash
uv run python -c "from odoo_mcp_server.server import main; print('ok')"
```

Expected: prints `ok` (no import error).

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest -v
```

Expected: all helper tests still pass.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/transport.py server/odoo_mcp_server/server.py
git commit -m "refactor: extract transport.py (XML-RPC + auth caching)"
```

---

## Task 7: Create `tools/` package and `tools/auth.py` (8 profile tools)

**Files:**
- Create: `server/odoo_mcp_server/tools/__init__.py`
- Create: `server/odoo_mcp_server/tools/auth.py`
- Modify: `server/odoo_mcp_server/server.py`

- [ ] **Step 1: Create empty `tools/__init__.py`**

```python
```

- [ ] **Step 2: Create `tools/auth.py`**

Move these 8 tools verbatim from `server.py`: `odoo_list_profiles`, `odoo_current_profile`, `odoo_add_profile`, `odoo_use_profile`, `odoo_remove_profile`, `odoo_connect_ad_hoc`, `odoo_test_connection`, `odoo_authenticate`.

Wrap them in a `register(mcp)` function. Replace `_state` with `transport._state`, `_proxy` with `transport.proxy`, `_connect` with `transport.connect`, `_invalidate_active` with `transport.invalidate_active`, `_active_creds` with `transport._active_creds`.

```python
"""Profile management and authentication MCP tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import profiles, transport


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_list_profiles() -> dict:
        """List configured Odoo profiles. Passwords never returned."""
        return {
            "profiles": profiles.list_profiles(),
            "active": profiles.current_profile_name(),
            "keyring": profiles.keyring_status(),
        }

    @mcp.tool()
    def odoo_current_profile() -> dict:
        """Return active profile (no password) + auth status."""
        name = profiles.current_profile_name()
        if not name:
            return {"active": None, "authenticated": False}
        p = profiles.get_profile(name) or {}
        return {
            "active": name,
            "url": p.get("url"),
            "db": p.get("db"),
            "user": p.get("user"),
            "authenticated": name in transport._state,
        }

    @mcp.tool()
    def odoo_add_profile(
        name: str,
        url: str,
        db: str,
        user: str,
        password: str,
        activate: bool = True,
    ) -> dict:
        """Create or update a named Odoo profile and persist it."""
        if not name or name.startswith("_"):
            raise ValueError("profile name must be non-empty and not start with _")
        profiles.set_profile(name, url, db, user, password)
        if activate:
            profiles.set_active(name)
            transport._state.pop(name, None)
        return {"name": name, "active": profiles.current_profile_name() == name}

    @mcp.tool()
    def odoo_use_profile(name: str) -> dict:
        """Switch active profile."""
        profiles.set_active(name)
        return odoo_current_profile()

    @mcp.tool()
    def odoo_remove_profile(name: str) -> dict:
        """Delete a saved profile and its stored password."""
        removed = profiles.remove_profile(name)
        transport._state.pop(name, None)
        return {"removed": removed, "active": profiles.current_profile_name()}

    @mcp.tool()
    def odoo_connect_ad_hoc(url: str, db: str, user: str, password: str) -> dict:
        """One-shot connection without persisting the profile."""
        profiles.set_adhoc(url, db, user, password)
        transport._state.pop(profiles.ADHOC_PROFILE_NAME, None)
        info = odoo_authenticate()
        return {"profile": profiles.ADHOC_PROFILE_NAME, **info}

    @mcp.tool()
    def odoo_test_connection(name: str | None = None) -> dict:
        """Authenticate against a profile (active if name=None) without changing active."""
        target = name or profiles.current_profile_name()
        if not target:
            return {"ok": False, "error": "no active profile"}
        p = profiles.get_profile(target)
        if not p:
            return {"ok": False, "error": f"profile not found: {target}"}
        try:
            common = transport.proxy(p["url"], "/xmlrpc/2/common")
            uid = common.authenticate(p["db"], p["user"], p["password"], {})
            if not uid:
                return {"ok": False, "error": "authentication returned no uid"}
            return {"ok": True, "profile": target, "uid": uid, "version": common.version()}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @mcp.tool()
    def odoo_authenticate() -> dict:
        """Force re-authentication of the active profile."""
        transport.invalidate_active()
        uid, _, db, _ = transport.connect()
        _, url, _, _, _ = transport._active_creds()
        common = transport.proxy(url, "/xmlrpc/2/common")
        return {"uid": uid, "db": db, "version": common.version()}
```

- [ ] **Step 3: Remove the 8 tools from `server.py` and call `auth.register`**

In `server.py`:

- Delete the bodies of all 8 tools listed above and their `@mcp.tool()` decorators.
- Add `from .tools import auth` near top.
- Add `auth.register(mcp)` immediately after `mcp = FastMCP("odoo-mcp")`.

- [ ] **Step 4: Verify import + tests still green**

```bash
uv run python -c "from odoo_mcp_server.server import main; print('ok')"
uv run pytest -v
```

Expected: `ok`, helper tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/__init__.py server/odoo_mcp_server/tools/auth.py server/odoo_mcp_server/server.py
git commit -m "refactor: move auth/profile tools to tools/auth.py"
```

---

## Task 8: Create `tools/crud.py` (10 CRUD/escape-hatch tools)

**Files:**
- Create: `server/odoo_mcp_server/tools/crud.py`
- Modify: `server/odoo_mcp_server/server.py`

- [ ] **Step 1: Create `tools/crud.py`**

Move these 10 tools from `server.py`: `odoo_search`, `odoo_search_count`, `odoo_read`, `odoo_search_read`, `odoo_fields_get`, `odoo_create`, `odoo_write`, `odoo_unlink`, `odoo_list_models`, `odoo_execute_kw`. Replace `_exec` with `transport.exec_kw`. Replace `_is_mixin_field` with `is_mixin_field` from `_helpers`.

```python
"""Core CRUD + introspection MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import is_mixin_field


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_search(
        model: str,
        domain: list | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[int]:
        """Search records, return list of IDs."""
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if order:
            kwargs["order"] = order
        return transport.exec_kw(model, "search", [domain or []], kwargs)

    @mcp.tool()
    def odoo_search_count(model: str, domain: list | None = None) -> int:
        """Count records matching domain."""
        return transport.exec_kw(model, "search_count", [domain or []])

    @mcp.tool()
    def odoo_read(model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read records by IDs. fields=None reads all."""
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        return transport.exec_kw(model, "read", [ids], kwargs)

    @mcp.tool()
    def odoo_search_read(
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        """Search + read in one call."""
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kwargs["fields"] = fields
        if order:
            kwargs["order"] = order
        return transport.exec_kw(model, "search_read", [domain or []], kwargs)

    @mcp.tool()
    def odoo_fields_get(
        model: str,
        attributes: list[str] | None = None,
        business_only: bool = False,
    ) -> dict:
        """Inspect model fields."""
        attrs = attributes or [
            "string", "type", "required", "readonly", "help", "selection", "relation",
        ]
        result = transport.exec_kw(model, "fields_get", [], {"attributes": attrs})
        if business_only:
            return {k: v for k, v in result.items() if not is_mixin_field(k)}
        return result

    @mcp.tool()
    def odoo_create(model: str, values: dict) -> int:
        """Create record. Returns new ID."""
        return transport.exec_kw(model, "create", [values])

    @mcp.tool()
    def odoo_write(model: str, ids: list[int], values: dict) -> bool:
        """Update records. Returns True on success."""
        return transport.exec_kw(model, "write", [ids, values])

    @mcp.tool()
    def odoo_unlink(model: str, ids: list[int]) -> bool:
        """Delete records. Returns True on success. Irreversible."""
        return transport.exec_kw(model, "unlink", [ids])

    @mcp.tool()
    def odoo_list_models(
        pattern: str | None = None,
        limit: int = 100,
        offset: int = 0,
        filter: str | None = None,
        filter_name: str | None = None,
    ) -> list[dict]:
        """List Odoo models matching technical name (ilike)."""
        pat = pattern or filter or filter_name
        domain: list = []
        if pat:
            domain = [["model", "ilike", pat]]
        return transport.exec_kw(
            "ir.model",
            "search_read",
            [domain],
            {
                "fields": ["model", "name", "modules"],
                "limit": limit,
                "offset": offset,
                "order": "model",
            },
        )

    @mcp.tool()
    def odoo_execute_kw(
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Generic escape hatch. Call any Odoo method via execute_kw."""
        return transport.exec_kw(model, method, args or [], kwargs or {})
```

- [ ] **Step 2: Remove the 10 tools from `server.py`, register `crud`**

In `server.py`:

- Delete the 10 tool definitions and any now-orphan imports (`re`, `Any`).
- Add `from .tools import auth, crud`.
- Add `crud.register(mcp)` after `auth.register(mcp)`.

- [ ] **Step 3: Verify import + tests**

```bash
uv run python -c "from odoo_mcp_server.server import main; print('ok')"
uv run pytest -v
```

Expected: `ok`, all helper tests pass.

- [ ] **Step 4: Commit**

```bash
git add server/odoo_mcp_server/tools/crud.py server/odoo_mcp_server/server.py
git commit -m "refactor: move CRUD tools to tools/crud.py"
```

---

## Task 9: Create `tools/discovery.py` (3 search/lookup tools)

**Files:**
- Create: `server/odoo_mcp_server/tools/discovery.py`
- Modify: `server/odoo_mcp_server/server.py`

- [ ] **Step 1: Create `tools/discovery.py`**

Move `odoo_multi_field_search`, `odoo_resolve_xmlid`, `odoo_chatter_read` from `server.py`. Replace `_strip_html` with `strip_html` from `_helpers`.

```python
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
        """Search a term across multiple text fields (OR), return search_read result."""
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
        """Resolve external id (module.name) to {"model": str, "res_id": int}."""
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
        """Read mail.message chatter for a record. Strips HTML from body."""
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
```

- [ ] **Step 2: Remove the 3 tools from `server.py`, register `discovery`**

In `server.py`:

- Delete the 3 tool definitions.
- Update import to `from .tools import auth, crud, discovery`.
- Add `discovery.register(mcp)` after `crud.register(mcp)`.

- [ ] **Step 3: Verify import + tests**

```bash
uv run python -c "from odoo_mcp_server.server import main; print('ok')"
uv run pytest -v
```

Expected: `ok`, helper tests pass.

- [ ] **Step 4: Commit**

```bash
git add server/odoo_mcp_server/tools/discovery.py server/odoo_mcp_server/server.py
git commit -m "refactor: move discovery tools to tools/discovery.py"
```

---

## Task 10: Slim `server.py` to bootstrap-only

**Files:**
- Modify: `server/odoo_mcp_server/server.py`

- [ ] **Step 1: Replace `server.py` with the slim bootstrap**

```python
"""Odoo MCP server bootstrap.

Multi-profile capable: switch between Odoo instances at runtime via
`odoo_use_profile` / `odoo_add_profile` / `odoo_connect_ad_hoc`.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import transport
from .tools import auth, crud, discovery

transport.load_env_file()

mcp = FastMCP("odoo-mcp")
auth.register(mcp)
crud.register(mcp)
discovery.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import + tests**

```bash
uv run python -c "from odoo_mcp_server.server import main; print('ok')"
uv run pytest -v
```

Expected: `ok`, helper tests pass.

- [ ] **Step 3: Sanity-check tool count**

```bash
uv run python -c "from odoo_mcp_server.server import mcp; import asyncio; print(len(asyncio.run(mcp.list_tools())))"
```

Expected: `21` (20 existing tools — they were all moved — plus none new yet; the 8+10+3 = 21 split is the auth/crud/discovery total).

If the number is wrong, a tool was missed during the move. Check `git log` for which file lost it.

- [ ] **Step 4: Commit**

```bash
git add server/odoo_mcp_server/server.py
git commit -m "refactor: slim server.py to module-registration bootstrap"
```

---

## Task 11: Live smoke regression check (refactor must not change behavior)

**Files:** none (verification only)

- [ ] **Step 1: Confirm there is an active profile pointing at `odoo-steriliza`**

```bash
uv run python -c "from odoo_mcp_server import profiles; print(profiles.current_profile_name())"
```

Expected: a non-empty profile name. If `None`, set up the local Odoo profile via `odoo_add_profile` (out of band) or `~/.claude/odoo-mcp.env` before continuing.

- [ ] **Step 2: Quick functional probe via the MCP tool registry**

```bash
uv run python - <<'PY'
import asyncio
from odoo_mcp_server.server import mcp

async def main():
    tools = await mcp.list_tools()
    names = sorted(t.name for t in tools)
    print(len(names))
    print("\n".join(names))

asyncio.run(main())
PY
```

Expected: `21` tools, names matching the README's table (no missing entries).

- [ ] **Step 3: Hit a live Odoo end-to-end**

```bash
ODOO_TEST_LIVE=1 uv run python - <<'PY'
from odoo_mcp_server import transport
print("uid", transport.connect()[0])
print("partners", transport.exec_kw("res.partner", "search_count", [[]]))
PY
```

Expected: prints a uid and a non-zero partner count.

- [ ] **Step 4: No commit (verification only). Proceed only if step 3 succeeds.**

If step 3 fails, the refactor introduced a regression — bisect the last 4 commits.

---

## Task 12: Add `odoo_metadata` tool (TDD — unit + integration)

**Files:**
- Create: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/odoo_mcp_server/server.py`
- Create: `server/tests/test_inspection.py`

- [ ] **Step 1: Write the failing test (unit, mocked)**

`tests/test_inspection.py`:

```python
from unittest.mock import patch

import pytest


def test_odoo_metadata_calls_get_metadata(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return [{
            "id": 7,
            "xmlid": "base.partner_admin",
            "noupdate": False,
            "create_uid": [1, "Admin"],
            "create_date": "2024-01-01",
            "write_uid": [1, "Admin"],
            "write_date": "2024-01-02",
        }]

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_metadata_impl("res.partner", [7])
    assert captured["call"] == ("res.partner", "get_metadata", [[7]], None)
    assert out[0]["xmlid"] == "base.partner_admin"
```

(Why `_odoo_metadata_impl`: tools registered via `@mcp.tool()` are awkward to call directly. Each `register(mcp)` body should expose the underlying function module-level prefixed with `_…_impl`, and the registered tool is a thin wrapper. See implementation below.)

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: ImportError (`tools.inspection` missing).

- [ ] **Step 3: Create `tools/inspection.py` with `odoo_metadata`**

```python
"""Inspection / introspection MCP tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import transport


def _odoo_metadata_impl(model: str, ids: list[int]) -> list[dict]:
    """Wrap Odoo `get_metadata`. Returns list of metadata dicts per id."""
    return transport.exec_kw(model, "get_metadata", [ids], None)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_metadata(model: str, ids: list[int]) -> list[dict]:
        """Wrap Odoo `get_metadata`.

        Returns: [{id, xmlid, noupdate, create_uid, create_date, write_uid, write_date}, ...]
        """
        return _odoo_metadata_impl(model, ids)
```

Also wire it up in `server.py`:

- Import: `from .tools import auth, crud, discovery, inspection`
- Add: `inspection.register(mcp)` after `discovery.register(mcp)`

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 16 passed (helper tests + 1 new).

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/odoo_mcp_server/server.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_metadata tool"
```

---

## Task 13: Add `odoo_view_get` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_inspection.py`:

```python
def test_odoo_view_get_default_returns_summary(monkeypatch):
    fake_response = {
        "name": "res.partner.form",
        "view_id": 42,
        "type": "form",
        "arch": '<form><sheet><group><field name="name" required="1"/></group></sheet></form>',
        "fields": {"name": {"type": "char", "string": "Name"}},
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        return fake_response

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_view_get_impl("res.partner", "form")
    assert out["model"] == "res.partner"
    assert out["view_type"] == "form"
    assert out["view_id"] == 42
    assert out["name"] == "res.partner.form"
    assert out["fields_summary"] == [{"name": "name", "required": "1"}]
    assert "arch" not in out
    assert "fields" not in out


def test_odoo_view_get_raw_includes_arch_and_fields(monkeypatch):
    fake_response = {
        "name": "x", "view_id": 1, "type": "form",
        "arch": "<form/>", "fields": {"a": {}},
    }
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", lambda *a, **k: fake_response)
    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_view_get_impl("m", "form", raw=True)
    assert out["arch"] == "<form/>"
    assert out["fields"] == {"a": {}}
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: 2 new tests fail (`_odoo_view_get_impl` missing).

- [ ] **Step 3: Implement**

In `tools/inspection.py`, add:

```python
from .._helpers import parse_view_arch


def _odoo_view_get_impl(
    model: str,
    view_type: str = "form",
    view_id: int | None = None,
    raw: bool = False,
) -> dict:
    """Wrap fields_view_get and reduce to a compact summary."""
    args: list = []
    kwargs: dict = {"view_type": view_type}
    if view_id is not None:
        kwargs["view_id"] = view_id
    res = transport.exec_kw(model, "fields_view_get", args, kwargs)
    out: dict = {
        "model": model,
        "view_type": view_type,
        "view_id": res.get("view_id"),
        "name": res.get("name"),
        "fields_summary": parse_view_arch(res.get("arch") or ""),
    }
    if raw:
        out["arch"] = res.get("arch")
        out["fields"] = res.get("fields")
    return out
```

In the `register(mcp)` body of `tools/inspection.py`, add:

```python
    @mcp.tool()
    def odoo_view_get(
        model: str,
        view_type: str = "form",
        view_id: int | None = None,
        raw: bool = False,
    ) -> dict:
        """Inspect an Odoo view.

        Default: returns {model, view_type, view_id, name, fields_summary}.
        raw=True: also returns full `arch` (XML) and `fields` dict.
        """
        return _odoo_view_get_impl(model, view_type, view_id, raw)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_view_get with parsed summary"
```

---

## Task 14: Add `odoo_modules_list` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing tests**

```python
def test_odoo_modules_list_default_state_installed(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["model"] = model
        captured["method"] = method
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [{"id": 1, "name": "base", "state": "installed"}]

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_modules_list_impl()
    assert captured["model"] == "ir.module.module"
    assert captured["method"] == "search_read"
    assert captured["args"] == [[["state", "=", "installed"]]]
    assert "name" in captured["kwargs"]["fields"]


def test_odoo_modules_list_state_all_skips_filter(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda model, method, args, kwargs=None: captured.update({"args": args}) or [])
    from odoo_mcp_server.tools import inspection
    inspection._odoo_modules_list_impl(state="all")
    assert captured["args"] == [[]]


def test_odoo_modules_list_pattern_appends_ilike(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda model, method, args, kwargs=None: captured.update({"args": args}) or [])
    from odoo_mcp_server.tools import inspection
    inspection._odoo_modules_list_impl(state="installed", pattern="account")
    assert captured["args"] == [[["state", "=", "installed"], ["name", "ilike", "account"]]]
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: 3 new tests fail.

- [ ] **Step 3: Implement**

```python
def _odoo_modules_list_impl(
    state: str = "installed",
    pattern: str | None = None,
) -> list[dict]:
    """List `ir.module.module` records."""
    domain: list = []
    if state != "all":
        domain.append(["state", "=", state])
    if pattern:
        domain.append(["name", "ilike", pattern])
    return transport.exec_kw(
        "ir.module.module",
        "search_read",
        [domain],
        {
            "fields": ["name", "shortdesc", "state", "installed_version"],
            "order": "name",
        },
    )
```

Inside `register(mcp)`:

```python
    @mcp.tool()
    def odoo_modules_list(
        state: str = "installed",
        pattern: str | None = None,
    ) -> list[dict]:
        """List Odoo modules.

        state in ("installed", "uninstalled", "to install", "to upgrade",
        "to remove", "all"). pattern filters by name (ilike).
        """
        return _odoo_modules_list_impl(state, pattern)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_modules_list tool"
```

---

## Task 15: Add `odoo_menu_tree` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing tests**

```python
def test_odoo_menu_tree_recurses_to_depth(monkeypatch):
    """Tree: root -> child -> grandchild. depth=2 includes only root + child."""
    db = {
        "root": {"id": 1, "name": "Root", "sequence": 1, "action": False, "child_id": [2]},
        "child": {"id": 2, "name": "Child", "sequence": 1, "action": False, "child_id": [3]},
        "grand": {"id": 3, "name": "Grand", "sequence": 1, "action": False, "child_id": []},
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        assert model == "ir.ui.menu"
        domain = args[0]
        if domain and domain[0] == ("parent_id", "=", False) or domain == [
            ("parent_id", "=", False), ("active", "=", True)
        ] or domain == [["parent_id", "=", False], ["active", "=", True]]:
            return [db["root"]]
        ids = next((c[2] for c in domain if c[0] == "id"), None)
        if ids == [2]:
            return [db["child"]]
        if ids == [3]:
            return [db["grand"]]
        return []

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_menu_tree_impl(depth=2)
    assert len(out) == 1
    assert out[0]["name"] == "Root"
    assert len(out[0]["children"]) == 1
    assert out[0]["children"][0]["name"] == "Child"
    assert out[0]["children"][0]["children"] == []  # depth cut here
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: failing test.

- [ ] **Step 3: Implement**

```python
def _odoo_menu_tree_impl(
    depth: int = 3,
    active_only: bool = True,
) -> list[dict]:
    """Build a depth-bounded tree from ir.ui.menu, starting at root menus."""
    base_filter: list = [["active", "=", True]] if active_only else []
    fields = ["id", "name", "sequence", "action", "child_id"]

    roots = transport.exec_kw(
        "ir.ui.menu",
        "search_read",
        [[["parent_id", "=", False]] + base_filter],
        {"fields": fields, "order": "sequence,name"},
    )

    def build(menu: dict, remaining: int) -> dict:
        out = {
            "id": menu["id"],
            "name": menu["name"],
            "sequence": menu["sequence"],
            "action": menu.get("action") or None,
            "children": [],
        }
        child_ids = menu.get("child_id") or []
        if remaining > 1 and child_ids:
            children = transport.exec_kw(
                "ir.ui.menu",
                "search_read",
                [[["id", "in", child_ids]] + base_filter],
                {"fields": fields, "order": "sequence,name"},
            )
            out["children"] = [build(c, remaining - 1) for c in children]
        return out

    return [build(r, depth) for r in roots]
```

Register:

```python
    @mcp.tool()
    def odoo_menu_tree(depth: int = 3, active_only: bool = True) -> list[dict]:
        """Build a depth-bounded ir.ui.menu tree starting at roots."""
        return _odoo_menu_tree_impl(depth, active_only)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 22 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_menu_tree (depth-bounded tree)"
```

---

## Task 16: Add `odoo_access_check` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing tests**

```python
def test_odoo_access_check_returns_allowed(monkeypatch):
    captured = {}
    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return True

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_access_check_impl("res.partner", "read")
    assert out == {"model": "res.partner", "operation": "read", "allowed": True}
    assert captured["call"] == (
        "res.partner", "check_access_rights",
        ["read"],
        {"raise_exception": False},
    )


def test_odoo_access_check_invalid_operation_raises():
    from odoo_mcp_server.tools import inspection
    with pytest.raises(ValueError):
        inspection._odoo_access_check_impl("res.partner", "explode")
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: 2 new tests fail.

- [ ] **Step 3: Implement**

```python
_ALLOWED_OPERATIONS = ("read", "write", "create", "unlink")


def _odoo_access_check_impl(
    model: str,
    operation: str = "read",
    raise_exception: bool = False,
) -> dict:
    """Wrap check_access_rights."""
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(
            f"operation must be one of {_ALLOWED_OPERATIONS}, got {operation!r}"
        )
    allowed = transport.exec_kw(
        model,
        "check_access_rights",
        [operation],
        {"raise_exception": raise_exception},
    )
    return {"model": model, "operation": operation, "allowed": bool(allowed)}
```

Register:

```python
    @mcp.tool()
    def odoo_access_check(
        model: str,
        operation: str = "read",
        raise_exception: bool = False,
    ) -> dict:
        """Check whether the current user can perform `operation` on `model`."""
        return _odoo_access_check_impl(model, operation, raise_exception)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_access_check tool"
```

---

## Task 17: Add `odoo_user_groups` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing test**

```python
def test_odoo_user_groups_default_uses_active_uid(monkeypatch):
    calls = []

    def fake_exec_kw(model, method, args, kwargs=None):
        calls.append((model, method, args, kwargs))
        if model == "res.users" and method == "read":
            return [{
                "id": 2, "login": "admin", "groups_id": [10, 11],
            }]
        if model == "res.groups" and method == "read":
            return [
                {"id": 10, "name": "Settings", "full_name": "Administration / Settings",
                 "category_id": [3, "Administration"]},
                {"id": 11, "name": "User", "full_name": "Sales / User",
                 "category_id": [4, "Sales"]},
            ]
        return []

    def fake_connect():
        return (2, None, "db", "pw")

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    monkeypatch.setattr(transport, "connect", fake_connect)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_user_groups_impl()
    assert out["uid"] == 2
    assert out["login"] == "admin"
    assert {g["name"] for g in out["groups"]} == {"Settings", "User"}
    assert out["groups"][0]["category"] == "Administration"
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: failing test.

- [ ] **Step 3: Implement**

```python
def _odoo_user_groups_impl(uid: int | None = None) -> dict:
    """List groups for `uid` (defaults to currently authenticated uid)."""
    if uid is None:
        uid, _, _, _ = transport.connect()
    users = transport.exec_kw(
        "res.users", "read", [[uid]], {"fields": ["login", "groups_id"]},
    )
    if not users:
        raise RuntimeError(f"user {uid} not found")
    user = users[0]
    group_ids = user.get("groups_id") or []
    groups = transport.exec_kw(
        "res.groups",
        "read",
        [group_ids],
        {"fields": ["name", "full_name", "category_id"]},
    ) if group_ids else []
    return {
        "uid": user["id"],
        "login": user["login"],
        "groups": [
            {
                "id": g["id"],
                "name": g["name"],
                "full_name": g.get("full_name"),
                "category": (g.get("category_id") or [None, None])[1],
            }
            for g in groups
        ],
    }
```

Register:

```python
    @mcp.tool()
    def odoo_user_groups(uid: int | None = None) -> dict:
        """Return {uid, login, groups: [{id, name, full_name, category}]}.

        uid=None uses the currently authenticated user.
        """
        return _odoo_user_groups_impl(uid)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 25 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_user_groups tool"
```

---

## Task 18: Add `odoo_company_list` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/inspection.py`
- Modify: `server/tests/test_inspection.py`

- [ ] **Step 1: Add failing test**

```python
def test_odoo_company_list_returns_user_companies(monkeypatch):
    def fake_exec_kw(model, method, args, kwargs=None):
        if model == "res.users" and method == "read":
            return [{"id": 2, "company_ids": [1, 2]}]
        if model == "res.company" and method == "read":
            return [
                {"id": 1, "name": "Main Co", "currency_id": [9, "EUR"], "parent_id": False},
                {"id": 2, "name": "Sub Co", "currency_id": [9, "EUR"], "parent_id": [1, "Main Co"]},
            ]
        return []

    def fake_connect():
        return (2, None, "db", "pw")

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    monkeypatch.setattr(transport, "connect", fake_connect)

    from odoo_mcp_server.tools import inspection
    out = inspection._odoo_company_list_impl()
    assert [c["name"] for c in out] == ["Main Co", "Sub Co"]
    assert out[0]["parent_id"] is None
    assert out[1]["parent_id"] == 1
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_inspection.py -v
```

Expected: failing test.

- [ ] **Step 3: Implement**

```python
def _odoo_company_list_impl() -> list[dict]:
    """List companies the current user has access to."""
    uid, _, _, _ = transport.connect()
    users = transport.exec_kw(
        "res.users", "read", [[uid]], {"fields": ["company_ids"]},
    )
    if not users:
        return []
    company_ids = users[0].get("company_ids") or []
    if not company_ids:
        return []
    companies = transport.exec_kw(
        "res.company",
        "read",
        [company_ids],
        {"fields": ["name", "currency_id", "parent_id"]},
    )
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "currency_id": (c.get("currency_id") or [None])[0],
            "parent_id": (c.get("parent_id") or [None])[0],
        }
        for c in companies
    ]
```

Register:

```python
    @mcp.tool()
    def odoo_company_list() -> list[dict]:
        """List companies the current user has access to."""
        return _odoo_company_list_impl()
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 26 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/inspection.py server/tests/test_inspection.py
git commit -m "feat(inspection): add odoo_company_list tool"
```

---

## Task 19: Add `tools/workflow.py` with `odoo_default_get` (TDD)

**Files:**
- Create: `server/odoo_mcp_server/tools/workflow.py`
- Modify: `server/odoo_mcp_server/server.py`
- Create: `server/tests/test_workflow.py`

- [ ] **Step 1: Add failing test**

`tests/test_workflow.py`:

```python
def test_odoo_default_get_explicit_fields(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return {"name": "New", "active": True}

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_default_get_impl("res.partner", ["name", "active"])
    assert captured["call"] == ("res.partner", "default_get", [["name", "active"]], None)
    assert out == {"name": "New", "active": True}


def test_odoo_default_get_none_fetches_all_fields(monkeypatch):
    captured = []

    def fake_exec_kw(model, method, args, kwargs=None):
        captured.append((model, method, args, kwargs))
        if method == "fields_get":
            return {"name": {}, "email": {}}
        if method == "default_get":
            return {"name": "X"}
        raise AssertionError(method)

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_default_get_impl("res.partner", None)
    assert out == {"name": "X"}
    assert captured[0][1] == "fields_get"
    assert captured[1][1] == "default_get"
    # ensures both 'name' and 'email' got passed in
    assert sorted(captured[1][2][0]) == ["email", "name"]
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: ImportError (`tools.workflow` missing).

- [ ] **Step 3: Create `tools/workflow.py`**

```python
"""Workflow MCP tools: button calls, onchange, defaults, copy."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import transport
from .._helpers import is_button_method


def _odoo_default_get_impl(
    model: str,
    fields: list[str] | None = None,
) -> dict:
    """Wrap default_get(fields). fields=None → all fields from fields_get."""
    if fields is None:
        all_fields = transport.exec_kw(model, "fields_get", [], {"attributes": ["type"]})
        fields = list(all_fields.keys())
    return transport.exec_kw(model, "default_get", [fields], None)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_default_get(
        model: str,
        fields: list[str] | None = None,
    ) -> dict:
        """Return Odoo's default values for `fields` on `model`.

        fields=None fetches all field names first via fields_get.
        """
        return _odoo_default_get_impl(model, fields)
```

Wire up in `server.py`:

- Import: `from .tools import auth, crud, discovery, inspection, workflow`
- Add: `workflow.register(mcp)` after `inspection.register(mcp)`

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 28 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/workflow.py server/odoo_mcp_server/server.py server/tests/test_workflow.py
git commit -m "feat(workflow): add odoo_default_get tool"
```

---

## Task 20: Add `odoo_copy` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/workflow.py`
- Modify: `server/tests/test_workflow.py`

- [ ] **Step 1: Add failing test**

```python
def test_odoo_copy_calls_copy_with_default(monkeypatch):
    captured = {}

    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return 99

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_copy_impl("res.partner", 7, default={"name": "Copy of X"})
    assert out == 99
    assert captured["call"] == ("res.partner", "copy", [7, {"name": "Copy of X"}], None)


def test_odoo_copy_default_none(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda m, meth, a, k=None: captured.update({"args": a}) or 1)
    from odoo_mcp_server.tools import workflow
    workflow._odoo_copy_impl("res.partner", 7)
    assert captured["args"] == [7, {}]
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: 2 failing tests.

- [ ] **Step 3: Implement**

In `tools/workflow.py`:

```python
def _odoo_copy_impl(
    model: str,
    id: int,
    default: dict | None = None,
) -> int:
    """Wrap Odoo copy(id, default). Returns the new record id."""
    return transport.exec_kw(model, "copy", [id, default or {}], None)
```

Register:

```python
    @mcp.tool()
    def odoo_copy(
        model: str,
        id: int,
        default: dict | None = None,
    ) -> int:
        """Duplicate a record. Returns the new id."""
        return _odoo_copy_impl(model, id, default)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 30 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/workflow.py server/tests/test_workflow.py
git commit -m "feat(workflow): add odoo_copy tool"
```

---

## Task 21: Add `odoo_call_button` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/workflow.py`
- Modify: `server/tests/test_workflow.py`

- [ ] **Step 1: Add failing tests**

```python
def test_odoo_call_button_executes(monkeypatch):
    captured = {}
    def fake_exec_kw(model, method, args, kwargs=None):
        captured["call"] = (model, method, args, kwargs)
        return {"type": "ir.actions.act_window_close"}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)
    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_call_button_impl("sale.order", [5], "action_confirm")
    assert out == {"type": "ir.actions.act_window_close"}
    assert captured["call"] == ("sale.order", "action_confirm", [[5]], {})


def test_odoo_call_button_rejects_non_whitelisted_method():
    from odoo_mcp_server.tools import workflow
    with pytest.raises(ValueError, match="must start with"):
        workflow._odoo_call_button_impl("res.partner", [1], "write")


def test_odoo_call_button_passes_kwargs(monkeypatch):
    captured = {}
    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw",
        lambda m, meth, a, k=None: captured.update({"kwargs": k}) or True)
    from odoo_mcp_server.tools import workflow
    workflow._odoo_call_button_impl("sale.order", [5], "action_confirm",
                                    kwargs={"context": {"foo": 1}})
    assert captured["kwargs"] == {"context": {"foo": 1}}
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: 3 failing tests.

- [ ] **Step 3: Implement**

```python
def _odoo_call_button_impl(
    model: str,
    ids: list[int],
    method: str,
    kwargs: dict | None = None,
) -> Any:
    """Call a button-style method on a recordset.

    Method name must start with action_/button_/toggle_. Returned value is
    whatever Odoo returns — typically True or an ir.actions.* dict.
    """
    if not is_button_method(method):
        raise ValueError(
            f"method {method!r} must start with one of action_/button_/toggle_"
        )
    return transport.exec_kw(model, method, [ids], kwargs or {})
```

Register:

```python
    @mcp.tool()
    def odoo_call_button(
        model: str,
        ids: list[int],
        method: str,
        kwargs: dict | None = None,
    ) -> Any:
        """Call an Odoo button method. Whitelisted to action_/button_/toggle_."""
        return _odoo_call_button_impl(model, ids, method, kwargs)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 33 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/workflow.py server/tests/test_workflow.py
git commit -m "feat(workflow): add odoo_call_button (whitelisted prefixes)"
```

---

## Task 22: Add `odoo_onchange` tool (TDD)

**Files:**
- Modify: `server/odoo_mcp_server/tools/workflow.py`
- Modify: `server/tests/test_workflow.py`

- [ ] **Step 1: Add failing test**

```python
def test_odoo_onchange_resolves_field_onchange_from_view(monkeypatch):
    calls = []

    fake_view = {
        "view_id": 42,
        "fields": {
            "company_type": {"on_change": "1"},
            "name": {"on_change": "0"},
        },
    }

    def fake_exec_kw(model, method, args, kwargs=None):
        calls.append((model, method, args, kwargs))
        if method == "fields_view_get":
            return fake_view
        if method == "onchange":
            assert args[0] == []
            assert args[1] == {"company_type": "company"}
            assert args[2] == "company_type"
            assert args[3] == {"company_type": "1", "name": "0"}
            return {"value": {"is_company": True}}
        raise AssertionError(method)

    from odoo_mcp_server import transport
    monkeypatch.setattr(transport, "exec_kw", fake_exec_kw)

    from odoo_mcp_server.tools import workflow
    out = workflow._odoo_onchange_impl(
        "res.partner",
        {"company_type": "company"},
        "company_type",
    )
    assert out == {"value": {"is_company": True}}
    assert calls[0][1] == "fields_view_get"
    assert calls[1][1] == "onchange"
```

- [ ] **Step 2: Run, verify fail**

```bash
uv run pytest tests/test_workflow.py -v
```

Expected: failing test.

- [ ] **Step 3: Implement**

```python
def _odoo_onchange_impl(
    model: str,
    values: dict,
    trigger_field: str,
    view_id: int | None = None,
) -> dict:
    """Run Odoo onchange. Auto-resolves field_onchange spec from form view."""
    view_kwargs: dict = {"view_type": "form"}
    if view_id is not None:
        view_kwargs["view_id"] = view_id
    view = transport.exec_kw(model, "fields_view_get", [], view_kwargs)
    fields_spec = view.get("fields") or {}
    field_onchange = {
        name: str(fdef.get("on_change") or "0")
        for name, fdef in fields_spec.items()
    }
    return transport.exec_kw(
        model,
        "onchange",
        [[], values, trigger_field, field_onchange],
        None,
    )
```

Register:

```python
    @mcp.tool()
    def odoo_onchange(
        model: str,
        values: dict,
        trigger_field: str,
        view_id: int | None = None,
    ) -> dict:
        """Run Odoo's onchange for `trigger_field` against `values`.

        Auto-resolves field_onchange spec from the form view. Returns
        Odoo's response dict {value, warning?, domain?}.
        """
        return _odoo_onchange_impl(model, values, trigger_field, view_id)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest -v
```

Expected: 34 passed.

- [ ] **Step 5: Commit**

```bash
git add server/odoo_mcp_server/tools/workflow.py server/tests/test_workflow.py
git commit -m "feat(workflow): add odoo_onchange (auto-resolves spec from view)"
```

---

## Task 23: Live integration smoke for Phase 1 tools

**Files:**
- Create: `server/tests/test_smoke_phase1.py`

- [ ] **Step 1: Write the live integration smoke**

```python
"""Live Phase 1 smoke. Set ODOO_TEST_LIVE=1 to run."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def admin_id():
    from odoo_mcp_server import transport
    rows = transport.exec_kw(
        "ir.model.data",
        "search_read",
        [[["module", "=", "base"], ["name", "=", "user_admin"]]],
        {"fields": ["res_id"], "limit": 1},
    )
    if not rows:
        pytest.skip("base.user_admin xmlid not found")
    user_rows = transport.exec_kw(
        "res.users", "read", [[rows[0]["res_id"]]], {"fields": ["partner_id"]}
    )
    return user_rows[0]["partner_id"][0]


def test_view_get_form(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_view_get_impl
    out = _odoo_view_get_impl("res.partner", "form")
    assert out["fields_summary"], "expected non-empty fields_summary"


def test_menu_tree_minimum_depth(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_menu_tree_impl
    tree = _odoo_menu_tree_impl(depth=2)
    assert tree, "expected at least one root menu"


def test_modules_list_contains_base(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_modules_list_impl
    mods = _odoo_modules_list_impl(state="installed", pattern="base")
    assert any(m["name"] == "base" for m in mods)


def test_access_check_read_partner(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_access_check_impl
    out = _odoo_access_check_impl("res.partner", "read")
    assert out["allowed"] is True


def test_user_groups_returns_admin_groups(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_user_groups_impl
    out = _odoo_user_groups_impl()
    assert out["groups"], "admin must have groups"


def test_company_list_at_least_one(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_company_list_impl
    out = _odoo_company_list_impl()
    assert len(out) >= 1


def test_metadata_resolves_xmlid(admin_id):
    from odoo_mcp_server.tools.inspection import _odoo_metadata_impl
    rows = _odoo_metadata_impl("res.partner", [admin_id])
    assert rows[0].get("xmlid") or rows[0].get("xmlids")


def test_default_get_returns_dict(admin_id):
    from odoo_mcp_server.tools.workflow import _odoo_default_get_impl
    out = _odoo_default_get_impl("res.partner")
    assert isinstance(out, dict)


def test_copy_then_unlink(admin_id):
    from odoo_mcp_server import transport
    from odoo_mcp_server.tools.workflow import _odoo_copy_impl
    new_id = _odoo_copy_impl("res.partner", admin_id, default={"name": "MCP smoke copy"})
    try:
        assert isinstance(new_id, int)
        rows = transport.exec_kw("res.partner", "read", [[new_id]], {"fields": ["name"]})
        assert rows[0]["name"].startswith("MCP smoke copy")
    finally:
        transport.exec_kw("res.partner", "unlink", [[new_id]], None)


def test_onchange_company_type():
    from odoo_mcp_server.tools.workflow import _odoo_onchange_impl
    out = _odoo_onchange_impl(
        "res.partner",
        {"company_type": "company"},
        "company_type",
    )
    assert isinstance(out, dict)
```

- [ ] **Step 2: Run integration suite against live Odoo**

Ensure the active profile points at `odoo-steriliza` (or any test instance), then:

```bash
ODOO_TEST_LIVE=1 uv run pytest tests/test_smoke_phase1.py -v
```

Expected: all 10 tests pass.

If a test fails because the live instance lacks data (e.g. no `base.user_admin`), `pytest.skip` is acceptable; do not weaken assertions to make it pass.

- [ ] **Step 3: Run unit suite without live mode (regression gate)**

```bash
uv run pytest -v
```

Expected: 34 unit tests pass; 10 integration tests skipped.

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_smoke_phase1.py
git commit -m "test: live integration smoke for Phase 1 tools"
```

---

## Task 24: Update README and TODO

**Files:**
- Modify: `README.md`
- Modify: `TODO.md`

- [ ] **Step 1: Add the 11 new tools to the README's tool table**

In `README.md`, in the table under "Features", add rows after `odoo_chatter_read`:

```markdown
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
```

- [ ] **Step 2: Move pending TODO items**

In `TODO.md`:

- Move the deferred items from `## Pendente` into the "Feito" log under the date `2026-05-09` for the Phase 1 entry.
- Add a new entry under `## Feito`:

```markdown
- 2026-05-09 — Fase 1 foundation tools: refactor `server.py` em modulos (`transport.py`, `_helpers.py`, `tools/{auth,crud,discovery,inspection,workflow}.py`); 11 tools novas (`odoo_metadata`, `odoo_view_get`, `odoo_menu_tree`, `odoo_modules_list`, `odoo_access_check`, `odoo_user_groups`, `odoo_company_list`, `odoo_call_button`, `odoo_onchange`, `odoo_default_get`, `odoo_copy`); `pytest` + tests unit + smoke integration (10 testes live).
```

- [ ] **Step 3: Commit**

```bash
git add README.md TODO.md
git commit -m "docs: README + TODO entries for Phase 1 foundation tools"
```

---

## Self-review checklist (run before declaring done)

- [ ] All 11 new tools from the spec have a task: `metadata` (T12), `view_get` (T13), `modules_list` (T14), `menu_tree` (T15), `access_check` (T16), `user_groups` (T17), `company_list` (T18), `default_get` (T19), `copy` (T20), `call_button` (T21), `onchange` (T22). ✓
- [ ] All target files in the spec are created: `transport.py` (T6), `_helpers.py` (T2-T5), `tools/auth.py` (T7), `tools/crud.py` (T8), `tools/discovery.py` (T9), `tools/inspection.py` (T12-T18), `tools/workflow.py` (T19-T22), slim `server.py` (T10). ✓
- [ ] No placeholder text (`TBD`, `add appropriate error handling`, "Similar to Task N"). ✓
- [ ] Type names consistent across tasks: `_odoo_*_impl` underscore-prefixed convention used in every TDD test. ✓
- [ ] Refactor regression gate exists (T11) before any new tool tasks land. ✓
- [ ] README + TODO updated (T24). ✓
