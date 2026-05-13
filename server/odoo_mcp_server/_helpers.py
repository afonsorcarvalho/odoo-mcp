"""Pure helpers — no transport / profile imports."""
from __future__ import annotations
import re as _re
import xml.etree.ElementTree as _ET

BUTTON_PREFIXES = ("action_", "button_", "toggle_")

# Attributes captured per <field> in parse_view_arch.
_FIELD_ATTRS = ("widget", "readonly", "required", "invisible", "string")


def is_button_method(name: str) -> bool:
    """True iff `name` starts with one of BUTTON_PREFIXES."""
    return name.startswith(BUTTON_PREFIXES)


def safe_context_merge(base: dict | None, extra: dict | None) -> dict:
    """Merge two contexts; extra wins. None-safe. Returns a new dict."""
    out: dict = {}
    if base:
        out.update(base)
    if extra:
        out.update(extra)
    return out


def parse_view_arch(arch_xml: str) -> list[dict]:
    """Tree-shake an Odoo view arch XML into a flat list of fields.

    Returns: [{"name": str, **{attr: str for attr in _FIELD_ATTRS if present}}, ...]
    Wrapper tags (sheet/group/notebook/page/header/etc.) are descended into;
    only <field> elements end up in the output. Returns [] on parse error.
    """
    try:
        root = _ET.fromstring(arch_xml)
    except (_ET.ParseError, TypeError):
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
