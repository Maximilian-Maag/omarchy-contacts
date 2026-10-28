"""Unit tests for omarchy-contacts' pure logic.

The shipped CLI has no ``.py`` extension (it is installed as ``omarchy-contacts``),
so it is loaded with a SourceFileLoader rather than imported by name.
"""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-contacts"

_loader = importlib.machinery.SourceFileLoader("omarchy_contacts", str(CLI))
_spec = importlib.util.spec_from_loader("omarchy_contacts", _loader)
ct = importlib.util.module_from_spec(_spec)
_loader.exec_module(ct)


def contact(*triples):
    c = {"properties": []}
    for name, value in triples:
        ct.add_value(c, name, value)
    return c


class EscapeTests(unittest.TestCase):
    def test_escape_plain(self):
        self.assertEqual(ct.escape_value("Ada Lovelace"), "Ada Lovelace")

    def test_escape_specials(self):
        self.assertEqual(ct.escape_value("a;b,c\\d"), "a\\;b\\,c\\\\d")

    def test_escape_newline(self):
        self.assertEqual(ct.escape_value("line1\nline2"), "line1\\nline2")

    def test_structured_semicolons_stay_bare(self):
        # N/ADR/ORG keep their component separators unescaped.
        self.assertEqual(ct.escape_value("Lovelace;Ada;;;", "N"), "Lovelace;Ada;;;")
        self.assertEqual(ct.escape_value("Street;City", "ADR"), "Street;City")
        self.assertEqual(ct.escape_value("Acme;R&D", "ORG"), "Acme;R&D")

    def test_categories_commas_stay_bare(self):
        self.assertEqual(ct.escape_value("a,b,c", "CATEGORIES"), "a,b,c")

    def test_unescape_roundtrip(self):
        for value in ["a;b,c\\d", "line1\nline2", "plain"]:
            self.assertEqual(ct.unescape_value(ct.escape_value(value)), value)

    def test_unescape_unknown_escape_keeps_char(self):
        self.assertEqual(ct.unescape_value("a\\qb"), "aqb")


class SplitTests(unittest.TestCase):
    def test_split_ignores_escaped_sep(self):
        self.assertEqual(ct.split_unescaped("a\\;b;c", ";"), ["a\\;b", "c"])

    def test_split_honours_quotes(self):
        self.assertEqual(ct.split_unescaped('a;"b;c";d', ";"), ["a", '"b;c"', "d"])

    def test_split_trailing_backslash_kept(self):
        # a backslash as the final character must not index past the end
        self.assertEqual(ct.split_unescaped("a\\", ";"), ["a\\"])

    def test_split_keeps_escaped_sep_at_end(self):
        self.assertEqual(ct.split_unescaped("a\\;", ";"), ["a\\;"])


class UnescapeBoundaryTests(unittest.TestCase):
    def test_escape_at_end_is_literal(self):
        self.assertEqual(ct.unescape_value("a\\"), "a\\")

    def test_last_escape_sequence_processed(self):
        self.assertEqual(ct.unescape_value("a\\n"), "a\n")


class FoldTests(unittest.TestCase):
    def test_unfold_reverses_fold(self):
        original = "FN:" + "Ada Lovelace " * 20
        self.assertEqual(ct.unfold(ct.fold_line(original)), original)

    def test_unfold_drops_line_break_and_one_space(self):
        # unfolding removes the CRLF and the single fold-space after it
        self.assertEqual(ct.unfold("FN:Ada\r\n Lovelace"), "FN:AdaLovelace")

    def test_short_line_is_not_folded(self):
        self.assertEqual(ct.fold_line("FN:Ada"), "FN:Ada")

    def test_long_line_folds_at_75(self):
        folded = ct.fold_line("NOTE:" + "x" * 200)
        self.assertIn("\r\n ", folded)
        for piece in folded.split("\r\n"):
            self.assertLessEqual(len(piece.encode()), 76)

    def test_exactly_75_bytes_is_not_folded(self):
        line = "N:" + "a" * 73          # 75 bytes
        self.assertEqual(ct.fold_line(line), line)

    def test_76_bytes_packs_to_75_then_wraps(self):
        # the first piece fills exactly FOLD_WIDTH, the remainder wraps
        line = "N:" + "a" * 74          # 76 bytes
        self.assertEqual(ct.fold_line(line), "N:" + "a" * 73 + "\r\n " + "a")


class ParseLineTests(unittest.TestCase):
    def test_name_params_value(self):
        name, params, value = ct.parse_line("EMAIL;TYPE=work:ada@example.org")
        self.assertEqual(name, "EMAIL")
        self.assertEqual(params["TYPE"], ["work"])
        self.assertEqual(value, "ada@example.org")

    def test_bare_param(self):
        _, params, _ = ct.parse_line("TEL;HOME:+1")
        self.assertEqual(params["HOME"], [""])

    def test_colon_inside_quotes(self):
        name, _, value = ct.parse_line('URL;X="a:b":http://x')
        self.assertEqual(name, "URL")
        self.assertEqual(value, "http://x")

    def test_blank_returns_none(self):
        self.assertIsNone(ct.parse_line("   "))

    def test_no_colon_returns_none(self):
        self.assertIsNone(ct.parse_line("NOVALUE"))


class SerializePropertyTests(unittest.TestCase):
    def test_roundtrip_of_params(self):
        line = ct.serialize_property("EMAIL", {"TYPE": ["work"]}, "ada@example.org")
        self.assertEqual(line, "EMAIL;TYPE=work:ada@example.org")

    def test_structured_value_not_escaped(self):
        line = ct.serialize_property("N", {}, "Lovelace;Ada;;;")
        self.assertEqual(line, "N:Lovelace;Ada;;;")


class VcardRoundtripTests(unittest.TestCase):
    def test_parse_ignores_begin_end_version(self):
        text = "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Ada\r\nEND:VCARD\r\n"
        parsed = ct.parse_vcard(text)
        self.assertEqual([p["name"] for p in parsed["properties"]], ["FN"])

    def test_uid_extracted(self):
        parsed = ct.parse_vcard("BEGIN:VCARD\r\nUID:abc\r\nFN:Ada\r\nEND:VCARD")
        self.assertEqual(parsed["uid"], "abc")

    def test_serialize_then_parse(self):
        original = contact(("FN", "Ada Lovelace"), ("EMAIL", "ada@example.org"))
        reparsed = ct.parse_vcard(ct.serialize_vcard(original))
        self.assertEqual(ct.get_value(reparsed, "FN"), "Ada Lovelace")

    def test_serialize_has_crlf_and_wrapper(self):
        text = ct.serialize_vcard(contact(("FN", "Ada")))
        self.assertTrue(text.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n"))
        self.assertTrue(text.endswith("END:VCARD\r\n"))

    def test_new_contact_builds_n_from_fn(self):
        c = ct.new_contact("Ada Lovelace")
        self.assertEqual(ct.get_value(c, "FN"), "Ada Lovelace")
        self.assertEqual(ct.get_value(c, "N"), "Lovelace;Ada;;;")

    def test_new_contact_assigns_uid(self):
        self.assertTrue(ct.new_contact()["uid"])


class PropertyAccessTests(unittest.TestCase):
    def test_get_value_default(self):
        self.assertIsNone(ct.get_value(contact(("FN", "a")), "EMAIL"))
        self.assertEqual(ct.get_value(contact(("FN", "a")), "EMAIL", "x"), "x")

    def test_get_values_multiple(self):
        c = contact(("EMAIL", "a@x"), ("EMAIL", "b@x"))
        self.assertEqual(ct.get_values(c, "EMAIL"), ["a@x", "b@x"])

    def test_set_value_replaces_all(self):
        c = contact(("EMAIL", "old"), ("EMAIL", "older"))
        ct.set_value(c, "EMAIL", "new")
        self.assertEqual(ct.get_values(c, "EMAIL"), ["new"])

    def test_set_value_adds_when_absent(self):
        c = contact(("FN", "a"))
        ct.set_value(c, "ORG", "Acme")
        self.assertEqual(ct.get_value(c, "ORG"), "Acme")

    def test_remove_value_all(self):
        c = contact(("EMAIL", "a"), ("EMAIL", "b"))
        ct.remove_value(c, "EMAIL")
        self.assertEqual(ct.get_values(c, "EMAIL"), [])

    def test_remove_value_specific(self):
        c = contact(("EMAIL", "a"), ("EMAIL", "b"))
        ct.remove_value(c, "EMAIL", "a")
        self.assertEqual(ct.get_values(c, "EMAIL"), ["b"])

    def test_add_value_sets_uid(self):
        c = {"properties": []}
        ct.add_value(c, "UID", "u1")
        self.assertEqual(c["uid"], "u1")


class OrderingTests(unittest.TestCase):
    def test_preferred_order_first(self):
        c = contact(("NOTE", "n"), ("FN", "Ada"), ("EMAIL", "a"))
        names = [p["name"] for p in ct.ordered_properties(c)]
        self.assertEqual(names[:3], ["FN", "EMAIL", "NOTE"])

    def test_unknown_property_kept(self):
        c = contact(("XNONSENSE", "x"), ("FN", "Ada"))
        self.assertIn("XNONSENSE", [p["name"] for p in ct.ordered_properties(c)])

    def test_display_order_puts_unknowns_last(self):
        c = contact(("XFOO", "1"), ("FN", "Ada"))
        self.assertEqual(ct.display_order(c)[-1]["name"], "XFOO")

    def test_property_label_includes_type(self):
        prop = {"name": "EMAIL", "params": {"TYPE": ["work", "pref"]}, "value": "x"}
        self.assertEqual(ct.property_label(prop), "EMAIL (work,pref)")


class FormatTests(unittest.TestCase):
    def test_formatted_name_prefers_fn(self):
        self.assertEqual(ct.formatted_name(contact(("FN", "Ada"), ("EMAIL", "a"))), "Ada")

    def test_formatted_name_falls_back_to_email(self):
        self.assertEqual(ct.formatted_name(contact(("EMAIL", "a@x"))), "a@x")

    def test_formatted_name_no_name(self):
        c = {"properties": [], "uid": "u"}
        self.assertEqual(ct.formatted_name(c), "u")

    def test_summary_joins_name_email_phone(self):
        c = contact(("FN", "Ada"), ("EMAIL", "a@x"), ("TEL", "+1"))
        self.assertEqual(ct.summary(c), "Ada  a@x  +1")

    def test_detail_lines_are_label_value(self):
        c = contact(("FN", "Ada"), ("EMAIL", "a@x"))
        rows = ct.detail_lines(c)
        self.assertIn(("FN", "Ada"), rows)
        self.assertIn(("EMAIL", "a@x"), rows)

    def test_list_lines(self):
        self.assertEqual(ct.list_lines([contact(("FN", "Ada"))]), ["Ada"])


class StoreTests(unittest.TestCase):
    def test_save_load_delete(self):
        with tempfile.TemporaryDirectory() as d:
            c = contact(("FN", "Ada"))
            c["uid"] = "u1"
            ct.save_contact(c, d, filename="u1")
            self.assertTrue(ct.vcf_files(d))
            loaded = ct.load_all(d)
            self.assertEqual(ct.formatted_name(loaded[0]), "Ada")
            self.assertTrue(ct.delete_contact(loaded[0]["_path"]))
            self.assertEqual(ct.load_all(d), [])

    def test_save_sanitises_filename(self):
        with tempfile.TemporaryDirectory() as d:
            c = contact(("FN", "Ada"))
            c["uid"] = "a/b c"
            path = ct.save_contact(c, d, filename="a/b c")
            self.assertEqual(path.suffix, ".vcf")
            self.assertNotIn("/", path.name)

    def test_vcf_files_of_missing_dir(self):
        self.assertEqual(ct.vcf_files("/nonexistent/dir"), [])

    def test_load_contact_missing(self):
        self.assertIsNone(ct.load_contact("/nonexistent/x.vcf"))

    def test_delete_contact_missing_returns_false(self):
        self.assertFalse(ct.delete_contact("/nonexistent/nope.vcf"))

    def test_list_collections(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "personal").mkdir()
            (pathlib.Path(d) / "work").mkdir()
            (pathlib.Path(d) / "afile").write_text("x")
            self.assertEqual(ct.list_collections(d), ["personal", "work"])

    def test_list_collections_missing_root(self):
        self.assertEqual(ct.list_collections("/nonexistent/root"), [])

    def test_collection_dir_under_root(self):
        self.assertEqual(ct.collection_dir("personal", "/root"),
                         pathlib.Path("/root/personal"))


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        ada = ct.new_contact("Ada Lovelace")
        ct.add_value(ada, "EMAIL", "ada@example.org")
        ct.save_contact(ada, self.dir, filename=ada["uid"])
        grace = ct.new_contact("Grace Hopper")
        ct.add_value(grace, "ORG", "US Navy")
        ct.save_contact(grace, self.dir, filename=grace["uid"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_matches_name_email_org(self):
        contacts = ct.load_all(self.dir)
        self.assertTrue(any(ct.matches(c, "lovelace") for c in contacts))
        self.assertTrue(any(ct.matches(c, "example.org") for c in contacts))
        self.assertTrue(any(ct.matches(c, "navy") for c in contacts))

    def test_search_no_query_returns_all(self):
        self.assertEqual(len(ct.search(self.dir, "")), 2)

    def test_search_filters(self):
        self.assertEqual(len(ct.search(self.dir, "ada")), 1)

    def test_find_one_by_uid(self):
        uid = ct.load_all(self.dir)[0]["uid"]
        self.assertEqual(ct.find_one(self.dir, uid)["uid"], uid)

    def test_find_one_ambiguous_returns_list(self):
        # an empty pattern matches every contact -> a list, not a single one
        self.assertIsInstance(ct.find_one(self.dir, ""), list)

    def test_find_one_none(self):
        self.assertIsNone(ct.find_one(self.dir, "zzz"))


class ThemeTests(unittest.TestCase):
    def test_load_theme_reads_hex(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "colors.toml"
            p.write_text('accent = "#82FB9C"\nbackground = "#0B0C16"\nname = "hackerman"\n')
            colors = ct.load_theme(p)
            self.assertEqual(colors["accent"], "#82FB9C")
            self.assertNotIn("name", colors)          # non-colour keys ignored

    def test_load_theme_missing(self):
        self.assertEqual(ct.load_theme("/nonexistent/colors.toml"), {})

    def test_theme_color_prefers_first_key(self):
        self.assertEqual(ct.theme_color({"fg": "#fff", "foreground": "#000"}, "foreground", "fg"),
                         "#000")

    def test_theme_color_fallback(self):
        self.assertEqual(ct.theme_color({}, "accent", fallback="#111"), "#111")


    def test_recorded_theme_name_reads_the_hook_stamp(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "omarchy-contacts").mkdir()
            (pathlib.Path(d) / "omarchy-contacts" / "active-theme").write_text("tokyo-night\n")
            with unittest.mock.patch.dict(os.environ, {"XDG_STATE_HOME": d}):
                self.assertEqual(ct.recorded_theme_name(), "tokyo-night")

    def test_recorded_theme_name_empty_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            with unittest.mock.patch.dict(os.environ, {"XDG_STATE_HOME": d}):
                self.assertEqual(ct.recorded_theme_name(), "")

    def test_resolve_theme_name_matches_an_installed_theme(self):
        with tempfile.TemporaryDirectory() as d:
            theme = pathlib.Path(d) / "hackerman"
            theme.mkdir()
            (theme / "colors.toml").write_text('accent = "#82FB9C"\n')
            colors = ct.load_theme(str(theme / "colors.toml"))
            with unittest.mock.patch.object(ct, "theme_search_dirs", lambda: [theme]):
                self.assertEqual(ct.resolve_theme_name(colors), "hackerman")

    def test_applied_theme_name_prefers_the_recorded_value(self):
        with unittest.mock.patch.object(ct, "recorded_theme_name", lambda: "tokyo-night"), \
             unittest.mock.patch.object(ct, "resolve_theme_name", lambda c: "hackerman"):
            self.assertEqual(ct.applied_theme_name({}), "tokyo-night")

    def test_applied_theme_name_falls_back_to_a_colour_match(self):
        with unittest.mock.patch.object(ct, "recorded_theme_name", lambda: ""), \
             unittest.mock.patch.object(ct, "resolve_theme_name", lambda c: "hackerman"):
            self.assertEqual(ct.applied_theme_name({}), "hackerman")


class ConfigTests(unittest.TestCase):
    def test_load_config_user_overrides_shipped(self):
        with tempfile.TemporaryDirectory() as d:
            user = pathlib.Path(d) / "contacts.json"
            user.write_text(json.dumps({"default_collection": "work"}))
            cfg = ct.load_config(user)
            self.assertEqual(cfg["default_collection"], "work")

    def test_save_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sub" / "contacts.json"
            ct.save_config({"default_collection": "x"}, path)
            self.assertEqual(json.loads(path.read_text())["default_collection"], "x")
            ct.save_config({"default_collection": "y"}, path)     # exist_ok
            self.assertEqual(json.loads(path.read_text())["default_collection"], "y")

    def test_default_config(self):
        self.assertEqual(ct.default_config()["default_collection"], "personal")
        self.assertEqual(ct.default_config()["servers"], [])

    def test_resolve_collection_override_wins(self):
        self.assertEqual(ct.resolve_collection({"default_collection": "personal"}, "work"), "work")

    def test_resolve_collection_config_then_default(self):
        self.assertEqual(ct.resolve_collection({"default_collection": "work"}, None), "work")
        self.assertEqual(ct.resolve_collection({}, None), "personal")


class ServerTests(unittest.TestCase):
    def test_server_for_none_when_empty(self):
        self.assertIsNone(ct.server_for({"servers": []}))

    def test_server_for_by_name_then_first(self):
        cfg = {"servers": [{"name": "a", "url": "u1"}, {"name": "b", "url": "u2"}]}
        self.assertEqual(ct.server_for(cfg, "b")["url"], "u2")
        self.assertEqual(ct.server_for(cfg)["url"], "u1")

    def test_password_from_env(self):
        with unittest.mock.patch.dict(os.environ, {"CT_SECRET": "hunter2"}):
            self.assertEqual(ct.password_for({"password_env": "CT_SECRET"}), "hunter2")

    def test_password_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "pw"
            f.write_text("secret\n")
            self.assertEqual(ct.password_for({"password_file": str(f)}), "secret")

    def test_password_file_missing(self):
        self.assertIsNone(ct.password_for({"password_file": "/nonexistent/pw"}))

    def test_password_none(self):
        self.assertIsNone(ct.password_for(None))
        self.assertIsNone(ct.password_for({}))


MULTISTATUS = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/dav/addressbooks/user/default/</d:href>
    <d:propstat><d:prop><d:displayname>Contacts</d:displayname></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/addressbooks/user/default/a.vcf</d:href>
    <d:propstat><d:prop><d:getetag>"1"</d:getetag>
      <card:address-data>BEGIN:VCARD&#13;FN:Ada&#13;END:VCARD</card:address-data>
    </d:prop></d:propstat>
  </d:response>
</d:multistatus>"""

PRINCIPAL = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response><d:propstat><d:prop>
    <d:current-user-principal><d:href>/dav/principals/user/</d:href></d:current-user-principal>
  </d:prop></d:propstat></d:response>
</d:multistatus>"""

HOME_SET = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response><d:propstat><d:prop>
    <card:addressbook-home-set><d:href>/dav/addressbooks/user/</d:href></card:addressbook-home-set>
  </d:prop></d:propstat></d:response>
</d:multistatus>"""


class CarddavTests(unittest.TestCase):
    def test_parse_multistatus_hrefs_and_local_names(self):
        entries = ct.parse_multistatus(MULTISTATUS)
        self.assertEqual(len(entries), 2)
        self.assertIn("displayname", entries[0]["props"])
        self.assertEqual(entries[1]["props"]["getetag"], '"1"')

    def test_parse_multistatus_bad_xml(self):
        self.assertEqual(ct.parse_multistatus("<not xml"), [])

    def test_discover_principal(self):
        self.assertEqual(ct.discover_principal(PRINCIPAL), "/dav/principals/user/")

    def test_discover_principal_absent(self):
        self.assertEqual(ct.discover_principal("<d:multistatus xmlns:d='DAV:'/>"), "")

    def test_addressbook_home(self):
        self.assertEqual(ct.addressbook_home(HOME_SET), "/dav/addressbooks/user/")

    def test_join_url(self):
        self.assertEqual(ct.join_url("https://h/dav", "ab/"),
                         "https://h/dav/ab/")

    def test_basic_auth_header(self):
        self.assertEqual(ct.basic_auth_header("u", "p"), "Basic " + __import__("base64")
                         .b64encode(b"u:p").decode())

    def test_report_mentions_carddav(self):
        self.assertIn("addressbook-query", ct.build_addressbook_report("/x"))

    def test_propfind_embeds_props(self):
        self.assertIn("<d:getetag/>", ct.build_propfind(["<d:getetag/>"]))

    def test_parse_vcards_multiple(self):
        text = ("BEGIN:VCARD\nFN:A\nEND:VCARD\n"
                "BEGIN:VCARD\nFN:B\nEND:VCARD\n")
        self.assertEqual(len(ct.parse_vcards(text)), 2)


class TuiHelperTests(unittest.TestCase):
    def test_key_action_known(self):
        self.assertEqual(ct.key_action("j"), "down")
        self.assertEqual(ct.key_action("\n"), "open")

    def test_key_action_unknown(self):
        self.assertIsNone(ct.key_action("Z"))

    def test_rgb_of_valid(self):
        self.assertEqual(ct.rgb_of("#0B0C16", (0, 0, 0)), (11, 12, 22))

    def test_rgb_of_invalid_uses_fallback(self):
        self.assertEqual(ct.rgb_of("nope", (1, 2, 3)), (1, 2, 3))
        self.assertEqual(ct.rgb_of("", (1, 2, 3)), (1, 2, 3))

