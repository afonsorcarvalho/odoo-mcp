from odoo_mcp_server._helpers import is_button_method, safe_context_merge, parse_view_arch


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


def test_parse_view_arch_none_returns_empty():
    assert parse_view_arch(None) == []


def test_parse_view_arch_false_returns_empty():
    assert parse_view_arch(False) == []


def test_parse_view_arch_field_without_name_skipped():
    assert parse_view_arch("<form><field/><field name=\"x\"/></form>") == [{"name": "x"}]


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
