"""Regression tests for omarchy-contacts. Each test names the bug it pins."""

import importlib.machinery
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-contacts"

_loader = importlib.machinery.SourceFileLoader("omarchy_contacts_reg", str(CLI))
_spec = importlib.util.spec_from_loader("omarchy_contacts_reg", _loader)
ct = importlib.util.module_from_spec(_spec)
_loader.exec_module(ct)


class StructuredPropertyTests(unittest.TestCase):
    def test_n_components_are_not_escaped(self):
        # Bug pinned: the ';' component separators in N were backslash-escaped,
        # so "Lovelace;Ada;;;" serialised as a single component.
        line = ct.serialize_property("N", {}, "Lovelace;Ada;;;")
        self.assertEqual(line, "N:Lovelace;Ada;;;")

    def test_adr_components_are_not_escaped(self):
        # Bug pinned: same for ADR's 7 components.
        line = ct.serialize_property("ADR", {"TYPE": ["home"]}, ";;123 Main;Town;ST;12345;US")
        self.assertEqual(line, "ADR;TYPE=home:;;123 Main;Town;ST;12345;US")

    def test_n_roundtrip(self):
        c = ct.new_contact("Ada Lovelace")
        reparsed = ct.parse_vcard(ct.serialize_vcard(c))
        self.assertEqual(ct.get_value(reparsed, "N"), "Lovelace;Ada;;;")

    def test_text_value_still_escapes_semicolon(self):
        # Bug pinned: the fix must not stop escaping ';' in ordinary text values.
        self.assertEqual(ct.serialize_property("NOTE", {}, "a;b"), "NOTE:a\\;b")


class FindTests(unittest.TestCase):
    def _dir(self):
        d = tempfile.TemporaryDirectory()
        ada = ct.new_contact("Ada Lovelace")
        ct.save_contact(ada, d.name, filename=ada["uid"])
        return d, ada

    def test_exact_uid_beats_substring(self):
        # Bug pinned: a pattern equal to a uid must return that contact even when
        # it is also a substring of another name.
        d, ada = self._dir()
        try:
            grace = ct.new_contact("Ada Grace Hopper")
            ct.save_contact(grace, d.name, filename=grace["uid"])
            self.assertEqual(ct.find_one(d.name, ada["uid"])["uid"], ada["uid"])
        finally:
            d.cleanup()

    def test_ambiguous_returns_list_not_arbitrary(self):
        # Bug pinned: a pattern matching several contacts silently returned the
        # first one; it must return the list so the caller can refuse.
        d = tempfile.TemporaryDirectory()
        try:
            for name in ("Ada One", "Ada Two"):
                c = ct.new_contact(name)
                ct.save_contact(c, d.name, filename=c["uid"])
            self.assertIsInstance(ct.find_one(d.name, "ada"), list)
        finally:
            d.cleanup()


class UnescapeTests(unittest.TestCase):
    def test_unknown_escape_keeps_char(self):
        # Bug pinned: an unknown \x escape used to drop the character entirely.
        self.assertEqual(ct.unescape_value("a\\zb"), "azb")

    def test_backslash_before_end(self):
        self.assertEqual(ct.unescape_value("a\\"), "a\\")


class SaveTests(unittest.TestCase):
    def test_filename_cannot_escape_the_directory(self):
        # Bug pinned: a uid containing "../" wrote outside the collection.
        with tempfile.TemporaryDirectory() as d:
            c = ct.new_contact("Ada")
            c["uid"] = "../../evil"
            path = ct.save_contact(c, d, filename=c["uid"])
            self.assertEqual(path.parent, pathlib.Path(d))
            self.assertNotIn("/", path.name)


class CliSafetyTests(unittest.TestCase):
    def _run(self, env, *args):
        return subprocess.run([sys.executable, str(CLI), *args], env=env,
                              capture_output=True, text=True, cwd=str(ROOT))

    def test_ambiguous_edit_refuses(self):
        # Bug pinned: 'set' with an ambiguous pattern edited an arbitrary contact;
        # it must refuse (exit 2) instead of guessing which one you meant.
        with tempfile.TemporaryDirectory() as t:
            env = {"XDG_DATA_HOME": t + "/data", "XDG_CONFIG_HOME": t + "/cfg",
                   "PATH": "/usr/bin:/bin"}
            self._run(env, "add", "--fn", "Ada One")
            self._run(env, "add", "--fn", "Ada Two")
            proc = self._run(env, "set", "ada", "ORG", "x")
            self.assertEqual(proc.returncode, 2)

    def test_ambiguous_show_lists_candidates(self):
        # show with an ambiguous pattern lists the matches without guessing.
        with tempfile.TemporaryDirectory() as t:
            env = {"XDG_DATA_HOME": t + "/data", "XDG_CONFIG_HOME": t + "/cfg",
                   "PATH": "/usr/bin:/bin"}
            self._run(env, "add", "--fn", "Ada One")
            self._run(env, "add", "--fn", "Ada Two")
            proc = self._run(env, "show", "ada")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("Ada One", proc.stdout)
            self.assertIn("Ada Two", proc.stdout)

    def test_set_reports_missing_contact(self):
        # Bug pinned: 'set' on a non-existent contact crashed with a traceback.
        with tempfile.TemporaryDirectory() as t:
            env = {"XDG_DATA_HOME": t + "/data", "XDG_CONFIG_HOME": t + "/cfg",
                   "PATH": "/usr/bin:/bin"}
            proc = self._run(env, "set", "nobody", "ORG", "x")
            self.assertEqual(proc.returncode, 1)
            self.assertNotIn("Traceback", proc.stderr)


class ParamQuotingTests(unittest.TestCase):
    """Bug pinned (#4): a quoted param value was re-emitted unquoted, so a value
    containing a comma split into two params on the next parse."""

    def test_quoted_comma_param_survives_import_export(self):
        text = ('BEGIN:VCARD\r\nVERSION:3.0\r\nFN:X\r\n'
                'TEL;TYPE="a,b":12345\r\nEND:VCARD\r\n')
        contact = ct.parse_vcard(text)
        tel = [p for p in contact["properties"] if p["name"] == "TEL"][0]
        self.assertEqual(tel["params"]["TYPE"], ["a,b"])            # one value on import
        reparsed = ct.parse_vcard(ct.serialize_vcard(contact))
        tel2 = [p for p in reparsed["properties"] if p["name"] == "TEL"][0]
        self.assertEqual(tel2["params"]["TYPE"], ["a,b"])           # still one after export

    def test_value_needing_quotes_is_quoted(self):
        self.assertEqual(ct.serialize_property("TEL", {"TYPE": ["a,b"]}, "12345"),
                         'TEL;TYPE="a,b":12345')

    def test_simple_value_is_not_quoted(self):
        self.assertEqual(ct.serialize_property("EMAIL", {"TYPE": ["work"]}, "a@x"),
                         "EMAIL;TYPE=work:a@x")


class SyncPushTests(unittest.TestCase):
    """Bug pinned (#3): a create-only PUT was refused with 412 for an existing
    object, yet 412 counted as success, so re-pushing an edited contact never
    updated the server and still reported success."""

    def _contact_dir(self, email):
        d = tempfile.TemporaryDirectory()
        c = ct.new_contact("Ada Lovelace")
        c["uid"] = "ada"
        ct.add_value(c, "EMAIL", email)
        ct.save_contact(c, d.name, filename="ada")
        return d

    def _push(self, directory, server):
        calls = []

        def fake(url, method="GET", body=None, headers=None, **kw):
            name = url.rsplit("/", 1)[-1]
            create_only = (headers or {}).get("If-None-Match") == "*"
            calls.append((name, create_only))
            if create_only and name in server:
                return 412, {}, "precondition failed"
            existed = name in server
            server[name] = body
            return (204 if existed else 201), {}, ""

        with unittest.mock.patch.object(ct, "http_request", side_effect=fake):
            pushed = ct.sync_push("https://cloud.example.org/remote.php/dav",
                                  "addressbooks/user/default/", str(directory), "u", "p")
        return pushed, calls

    def test_new_contact_is_created(self):
        d = self._contact_dir("ada@example.org")
        try:
            server = {}
            pushed, _ = self._push(d.name, server)
            self.assertEqual(pushed, 1)
            self.assertIn("ada@example.org", server["ada.vcf"])
        finally:
            d.cleanup()

    def test_existing_contact_is_actually_updated(self):
        d = self._contact_dir("new@example.org")
        try:
            server = {"ada.vcf": "BEGIN:VCARD\r\nEMAIL:old@example.org\r\nEND:VCARD\r\n"}
            pushed, calls = self._push(d.name, server)
            self.assertEqual(pushed, 1)                          # counted exactly once
            self.assertTrue(any(not create for _, create in calls))   # an update PUT ran
            self.assertIn("new@example.org", server["ada.vcf"])  # body really changed
            self.assertNotIn("old@example.org", server["ada.vcf"])
        finally:
            d.cleanup()

    def test_a_permanent_refusal_is_not_counted(self):
        d = self._contact_dir("ada@example.org")
        try:
            def refuse(url, method="GET", body=None, headers=None, **kw):
                return 412, {}, ""

            with unittest.mock.patch.object(ct, "http_request", side_effect=refuse):
                pushed = ct.sync_push("https://h/dav", "ab/", d.name, "u", "p")
            self.assertEqual(pushed, 0)
        finally:
            d.cleanup()


if __name__ == "__main__":
    unittest.main()
