"""Regression tests for omarchy-contacts. Each test names the bug it pins."""

import importlib.machinery
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
