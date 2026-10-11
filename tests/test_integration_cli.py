"""Integration tests: drive the shipped CLI end-to-end against a throwaway store.

Each test runs the real binary as a subprocess with its own XDG_DATA_HOME /
XDG_CONFIG_HOME / XDG_STATE_HOME, so nothing touches the user's address book.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "bin/omarchy-contacts"


class CliIntegrationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = pathlib.Path(self.tmp.name) / "data"
        self.cfg = pathlib.Path(self.tmp.name) / "cfg"
        self.state = pathlib.Path(self.tmp.name) / "state"
        self.env = {
            "XDG_DATA_HOME": str(self.data),
            "XDG_CONFIG_HOME": str(self.cfg),
            "XDG_STATE_HOME": str(self.state),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.tmp.name,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], env=self.env,
                              capture_output=True, text=True, cwd=str(ROOT))

    def add(self, name, email=None):
        args = ["add", "--fn", name]
        if email:
            args += ["--email", email]
        return self.run_cli(*args).stdout.strip()

    def collection_dir(self, name="personal"):
        return self.data / "omarchy-contacts" / name

    # ── add / list / show ────────────────────────────────────────────────
    def test_add_prints_uid_and_writes_a_file(self):
        uid = self.add("Ada Lovelace", "ada@example.org")
        self.assertTrue(uid)
        self.assertTrue(list(self.collection_dir().glob("*.vcf")))

    def test_list_shows_the_contact(self):
        self.add("Ada Lovelace", "ada@example.org")
        out = self.run_cli("list").stdout
        self.assertIn("Ada Lovelace", out)
        self.assertIn("ada@example.org", out)

    def test_list_json(self):
        self.add("Ada Lovelace")
        payload = json.loads(self.run_cli("list", "--json").stdout)
        self.assertEqual(payload[0]["name"], "Ada Lovelace")

    def test_list_query_filters(self):
        self.add("Ada Lovelace")
        self.add("Grace Hopper")
        out = self.run_cli("list", "--query", "grace").stdout
        self.assertIn("Grace", out)
        self.assertNotIn("Ada", out)

    def test_show_detail(self):
        self.add("Ada Lovelace", "ada@example.org")
        out = self.run_cli("show", "ada").stdout
        self.assertIn("FN: Ada Lovelace", out)
        self.assertIn("EMAIL: ada@example.org", out)

    # ── set / unset / rm ─────────────────────────────────────────────────
    def test_set_adds_a_property(self):
        self.add("Ada Lovelace")
        self.assertEqual(self.run_cli("set", "ada", "ORG", "Analytical").returncode, 0)
        self.assertIn("ORG: Analytical", self.run_cli("show", "ada").stdout)

    def test_set_updates_existing(self):
        self.add("Ada Lovelace", "old@example.org")
        self.run_cli("set", "ada", "EMAIL", "new@example.org")
        self.assertIn("new@example.org", self.run_cli("show", "ada").stdout)

    def test_unset_removes_a_property(self):
        uid = self.add("Ada Lovelace", "a@example.org")
        self.run_cli("set", uid, "TEL", "+1")
        self.assertIn("TEL: +1", self.run_cli("show", uid).stdout)
        self.run_cli("unset", uid, "TEL")
        self.assertNotIn("TEL:", self.run_cli("show", uid).stdout)

    def test_unset_specific_value_keeps_the_rest(self):
        uid = self.add("Ada Lovelace")
        self.run_cli("set", uid, "EMAIL", "keep@example.org")
        self.run_cli("unset", uid, "EMAIL", "other@example.org")   # no such value
        self.assertIn("keep@example.org", self.run_cli("show", uid).stdout)

    def test_rm_deletes(self):
        self.add("Ada Lovelace")
        self.assertEqual(self.run_cli("rm", "ada").returncode, 0)
        self.assertEqual(len(list(self.collection_dir().glob("*.vcf"))), 0)

    # ── import / export ──────────────────────────────────────────────────
    def test_export_then_import(self):
        self.add("Ada Lovelace", "ada@example.org")
        exported = self.run_cli("export", "ada").stdout
        self.assertIn("BEGIN:VCARD", exported)
        vcf = pathlib.Path(self.tmp.name) / "in.vcf"
        vcf.write_text(exported)
        self.assertIn("imported 1", self.run_cli("import", str(vcf)).stdout)

    def test_export_all(self):
        self.add("Ada Lovelace")
        self.add("Grace Hopper")
        out = self.run_cli("export").stdout
        self.assertEqual(out.count("BEGIN:VCARD"), 2)

    # ── collections / config ─────────────────────────────────────────────
    def test_collections_lists_the_default(self):
        self.add("Ada Lovelace")
        self.assertIn("personal", self.run_cli("collections").stdout)

    def test_collection_override(self):
        self.run_cli("--collection", "work", "add", "--fn", "Worker")
        self.assertIn("Worker", self.run_cli("--collection", "work", "list").stdout)
        self.assertNotIn("Worker", self.run_cli("list").stdout)

    def test_default_collection_from_config(self):
        (self.cfg / "omarchy-contacts").mkdir(parents=True)
        (self.cfg / "omarchy-contacts/contacts.json").write_text(
            json.dumps({"default_collection": "work"}))
        self.run_cli("add", "--fn", "CfgDefault")
        self.assertTrue(list(self.collection_dir("work").glob("*.vcf")))

    # ── theme ────────────────────────────────────────────────────────────
    def test_theme_reads_applied_colors(self):
        theme = self.state / "omarchy/current/theme"
        theme.mkdir(parents=True)
        (theme / "colors.toml").write_text('accent = "#82FB9C"\n')
        out = self.run_cli("theme", "--json").stdout
        self.assertEqual(json.loads(out)["accent"], "#82FB9C")


if __name__ == "__main__":
    unittest.main()
