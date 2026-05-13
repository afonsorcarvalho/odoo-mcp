"""Profile management and authentication MCP tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .. import profiles, transport


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def odoo_list_profiles() -> dict:
        """List configured Odoo profiles. Passwords never returned.

        Returns {profiles: [...], active: str|None, keyring: {...}}.
        """
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
        transport_flag: str | None = None,
    ) -> dict:
        """Create or update a named Odoo profile and persist it.

        Password stored in OS keyring (or fallback file if keyring unavailable).
        Profile metadata (url/db/user/transport) stored in `~/.claude/odoo-mcp.profiles.json`.
        activate=True makes this the active profile (default).

        transport_flag: optional 'xmlrpc' (default) or 'jsonrpc'. Use 'jsonrpc' when
            the Odoo instance has a server-side XML-RPC bug (e.g. website module
            AttributeError) that prevents XML-RPC authentication.
        """
        if not name or name.startswith("_"):
            raise ValueError("profile name must be non-empty and not start with _")
        profiles.set_profile(name, url, db, user, password, transport=transport_flag)
        if activate:
            profiles.set_active(name)
            transport._state.pop(name, None)
        return {"name": name, "active": profiles.current_profile_name() == name}

    @mcp.tool()
    def odoo_use_profile(name: str) -> dict:
        """Switch active profile. Subsequent tool calls hit the new Odoo instance."""
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
        """One-shot connection without persisting the profile.

        Sets a transient `_adhoc` profile as active. Lost on server restart.
        Use `odoo_add_profile` instead if you want to keep the credentials.
        """
        profiles.set_adhoc(url, db, user, password)
        transport._state.pop(profiles.ADHOC_PROFILE_NAME, None)
        info = odoo_authenticate()
        return {"profile": profiles.ADHOC_PROFILE_NAME, **info}

    @mcp.tool()
    def odoo_test_connection(name: str | None = None) -> dict:
        """Authenticate against a profile (active if name=None) without changing active.

        Returns {ok, uid?, version?, error?}.
        """
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
        """Force re-authentication of the active profile. Returns uid + server version."""
        transport.invalidate_active()
        uid, _, db, _ = transport.connect()
        _, url, _, _, _, _ = transport._active_creds()
        common = transport.proxy(url, "/xmlrpc/2/common")
        return {"uid": uid, "db": db, "version": common.version()}
