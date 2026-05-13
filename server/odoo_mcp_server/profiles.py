"""Profile storage for multi-Odoo instance support.

Profiles live in `~/.claude/odoo-mcp.profiles.json` (no passwords).
Passwords are stored in the OS keyring under service `odoo-mcp`, username = profile name.
If `keyring` is unavailable or fails (e.g. headless Linux without secret service),
the password is written to a sibling file `odoo-mcp.profiles.secrets.json` (chmod 600 best-effort).
"""
from __future__ import annotations

import json
import logging
import os
import stat
from typing import Any

log = logging.getLogger("odoo-mcp.profiles")

PROFILES_PATH = os.path.join(os.path.expanduser("~"), ".claude", "odoo-mcp.profiles.json")
SECRETS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "odoo-mcp.profiles.secrets.json")
KEYRING_SERVICE = "odoo-mcp"
ENV_PROFILE_NAME = "_env"
ADHOC_PROFILE_NAME = "_adhoc"

try:
    import keyring  # type: ignore
    import keyring.errors  # type: ignore
    _KEYRING_OK = True
except Exception as e:  # pragma: no cover
    log.warning("keyring unavailable, falling back to plaintext secrets file: %s", e)
    keyring = None  # type: ignore
    _KEYRING_OK = False


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)


def _read_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning("failed reading %s: %s", path, e)
        return {}


def _write_json(path: str, data: dict, restrict: bool = False) -> None:
    _ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)
    if restrict and os.name == "posix":
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def _load_secrets() -> dict[str, str]:
    return _read_json(SECRETS_PATH)


def _save_secrets(secrets: dict[str, str]) -> None:
    _write_json(SECRETS_PATH, secrets, restrict=True)


def _password_get(name: str) -> str | None:
    if _KEYRING_OK:
        try:
            v = keyring.get_password(KEYRING_SERVICE, name)
            if v is not None:
                return v
        except Exception as e:
            log.warning("keyring get failed for %s: %s", name, e)
    return _load_secrets().get(name)


def _password_set(name: str, password: str) -> None:
    if _KEYRING_OK:
        try:
            keyring.set_password(KEYRING_SERVICE, name, password)
            return
        except Exception as e:
            log.warning("keyring set failed for %s: %s — using fallback file", name, e)
    secrets = _load_secrets()
    secrets[name] = password
    _save_secrets(secrets)


def _password_delete(name: str) -> None:
    if _KEYRING_OK:
        try:
            keyring.delete_password(KEYRING_SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
        except Exception as e:
            log.warning("keyring delete failed for %s: %s", name, e)
    secrets = _load_secrets()
    if name in secrets:
        del secrets[name]
        _save_secrets(secrets)


def _load_index() -> dict[str, Any]:
    data = _read_json(PROFILES_PATH)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("profiles", {})
    data.setdefault("active", None)
    return data


def _save_index(data: dict[str, Any]) -> None:
    _write_json(PROFILES_PATH, data)


_adhoc_state: dict[str, Any] = {"profile": None}


_VALID_TRANSPORTS = {"xmlrpc", "jsonrpc"}


def list_profiles() -> list[dict[str, Any]]:
    """Return profiles as list of {name, url, db, user, transport, active} (no password)."""
    idx = _load_index()
    active = current_profile_name()
    out: list[dict[str, Any]] = []
    for name, p in sorted(idx["profiles"].items()):
        out.append({
            "name": name,
            "url": p.get("url"),
            "db": p.get("db"),
            "user": p.get("user"),
            "transport": p.get("transport", "xmlrpc"),
            "active": name == active,
        })
    if _adhoc_state["profile"]:
        p = _adhoc_state["profile"]
        out.append({
            "name": ADHOC_PROFILE_NAME,
            "url": p.get("url"),
            "db": p.get("db"),
            "user": p.get("user"),
            "active": active == ADHOC_PROFILE_NAME,
            "transient": True,
        })
    if active == ENV_PROFILE_NAME and not any(o["name"] == ENV_PROFILE_NAME for o in out):
        env = _env_profile()
        if env:
            out.append({**{k: v for k, v in env.items() if k != "password"}, "name": ENV_PROFILE_NAME, "active": True, "transient": True})
    return out


def _env_profile() -> dict[str, str] | None:
    keys = {"url": "ODOO_URL", "db": "ODOO_DB", "user": "ODOO_USER", "password": "ODOO_PASSWORD"}
    vals = {k: os.environ.get(v, "") for k, v in keys.items()}
    if all(vals.values()):
        return vals
    return None


def get_profile(name: str) -> dict[str, str] | None:
    """Return full profile {url, db, user, password, transport} or None."""
    if name == ADHOC_PROFILE_NAME:
        return _adhoc_state["profile"]
    if name == ENV_PROFILE_NAME:
        return _env_profile()
    idx = _load_index()
    p = idx["profiles"].get(name)
    if not p:
        return None
    pw = _password_get(name)
    if pw is None:
        return None
    return {
        "url": p["url"],
        "db": p["db"],
        "user": p["user"],
        "password": pw,
        "transport": p.get("transport", "xmlrpc"),
    }


def set_profile(
    name: str,
    url: str,
    db: str,
    user: str,
    password: str | None,
    transport: str | None = None,
) -> None:
    """Add or update a profile. password=None keeps existing password.

    transport: optional 'xmlrpc' or 'jsonrpc'. None keeps existing or defaults to 'xmlrpc'.
    """
    if name in (ENV_PROFILE_NAME, ADHOC_PROFILE_NAME):
        raise ValueError(f"reserved profile name: {name}")
    if transport is not None and transport not in _VALID_TRANSPORTS:
        raise ValueError(f"invalid transport {transport!r}: must be 'xmlrpc' or 'jsonrpc'")
    idx = _load_index()
    existing = idx["profiles"].get(name, {})
    entry: dict[str, str] = {"url": url.rstrip("/"), "db": db, "user": user}
    # Resolve transport: explicit arg > existing stored value > default "xmlrpc"
    resolved_transport = transport or existing.get("transport", "xmlrpc")
    entry["transport"] = resolved_transport
    idx["profiles"][name] = entry
    _save_index(idx)
    if password is not None:
        _password_set(name, password)


def remove_profile(name: str) -> bool:
    if name in (ENV_PROFILE_NAME, ADHOC_PROFILE_NAME):
        raise ValueError(f"cannot remove reserved profile: {name}")
    idx = _load_index()
    if name not in idx["profiles"]:
        return False
    del idx["profiles"][name]
    if idx.get("active") == name:
        idx["active"] = next(iter(idx["profiles"]), None)
    _save_index(idx)
    _password_delete(name)
    return True


def set_active(name: str) -> None:
    if name == ADHOC_PROFILE_NAME:
        if not _adhoc_state["profile"]:
            raise RuntimeError("no ad-hoc profile defined")
        idx = _load_index()
        idx["active"] = ADHOC_PROFILE_NAME
        _save_index(idx)
        return
    if name == ENV_PROFILE_NAME:
        if not _env_profile():
            raise RuntimeError("env vars ODOO_URL/ODOO_DB/ODOO_USER/ODOO_PASSWORD not all set")
        idx = _load_index()
        idx["active"] = ENV_PROFILE_NAME
        _save_index(idx)
        return
    idx = _load_index()
    if name not in idx["profiles"]:
        raise RuntimeError(f"unknown profile: {name}")
    idx["active"] = name
    _save_index(idx)


def current_profile_name() -> str | None:
    """Resolve active profile name. Falls back to env vars if nothing configured."""
    idx = _load_index()
    name = idx.get("active")
    if name == ADHOC_PROFILE_NAME and _adhoc_state["profile"]:
        return ADHOC_PROFILE_NAME
    if name == ENV_PROFILE_NAME:
        return ENV_PROFILE_NAME if _env_profile() else None
    if name and name in idx["profiles"]:
        return name
    if idx["profiles"]:
        first = next(iter(sorted(idx["profiles"])))
        return first
    if _env_profile():
        return ENV_PROFILE_NAME
    return None


def set_adhoc(url: str, db: str, user: str, password: str) -> None:
    _adhoc_state["profile"] = {"url": url.rstrip("/"), "db": db, "user": user, "password": password}
    idx = _load_index()
    idx["active"] = ADHOC_PROFILE_NAME
    _save_index(idx)


def keyring_status() -> dict[str, Any]:
    return {"keyring_available": _KEYRING_OK, "fallback_file": SECRETS_PATH if not _KEYRING_OK else None}
