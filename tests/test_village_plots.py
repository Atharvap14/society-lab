"""Exact actual-source extraction checks; unavailable release data stays skipped."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("village_plots", ROOT / "scripts" / "build-village-plots.py")
plots = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(plots)


class RealVillageExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / ".runtime" / "lab.sqlite3"
        if not path.is_file(): raise unittest.SkipTest("Actual locally saved September source is not bundled in a fresh checkout")
        try: cls.record = plots.load_exact_dataset(path, plots.SEPTEMBER_REF)
        except ValueError as error:
            if "unavailable" in str(error): raise unittest.SkipTest(str(error))
            raise

    def test_exact_source_ids_counts_and_edge_witnesses(self):
        packet = plots.extract_descriptive_series(self.record)
        ms = {m["id"]: m for m in self.record["payload"]["messages"]}
        self.assertEqual(packet["source_ref"], plots.SEPTEMBER_REF)
        self.assertEqual(len(ms), 2000)
        self.assertEqual(packet["counts"]["agent_posts"], 1983)
        self.assertEqual(packet["counts"]["user_posts"], 17)
        self.assertEqual(packet["counts"]["unknown_audience"], 2000)
        self.assertEqual({m["message_id"] for m in packet["original_message_coordinates"]}, set(ms))
        self.assertEqual(sum(sum(a["posts_by_bin"]) for a in packet["agents"]), 1983)
        names = {a["id"]: a["name"] for a in packet["agents"]}
        for edge in packet["name_cooccurrence_edges"]:
            self.assertEqual(edge["message_count"], len(edge["witnesses"]))
            self.assertEqual(len({w["message_id"] for w in edge["witnesses"]}), edge["message_count"])
            for w in edge["witnesses"]:
                original = ms[w["message_id"]]
                self.assertEqual(original["speaker_type"], "agent")
                self.assertEqual(w["timestamp"], original["timestamp"])
                self.assertEqual(w["source"], original["source"])
                self.assertIn(names[edge["left"]].lower(), original["content"].lower())
                self.assertIn(names[edge["right"]].lower(), original["content"].lower())
        self.assertEqual(packet["model_calls"], 0); self.assertEqual(packet["database_writes"], 0)
        self.assertFalse(packet["raw_source_reread"])

    def test_changed_body_and_typed_exact_pin_reject(self):
        changed = copy.deepcopy(self.record); changed["payload"]["messages"][0]["content"] += "changed"
        with self.assertRaisesRegex(ValueError, "changed"): plots.extract_descriptive_series(changed)
        for version in (True, 1.0):
            with self.assertRaisesRegex(ValueError, "typed"): plots.load_exact_dataset(ROOT / ".runtime" / "lab.sqlite3", plots.SEPTEMBER_REF | {"version": version})
        with self.assertRaisesRegex(ValueError, "mismatch"):
            plots.load_exact_dataset(ROOT / ".runtime" / "lab.sqlite3", plots.SEPTEMBER_REF | {"hash": "0" * 64})

    def test_no_registry_mutation_or_implicit_author_edge(self):
        # Copy this exact actual record into an isolated read fixture; unrelated
        # legitimate production job commits cannot create a false mutation alarm.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actual-source.sqlite3"
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE objects(id,version,kind,created,payload,hash)")
                conn.execute("INSERT INTO objects VALUES(?,?,?,?,?,?)", (self.record["id"], self.record["version"], "dataset", "retained-exact-source", json.dumps(self.record["payload"], ensure_ascii=False), self.record["hash"]))
                conn.commit()
            finally: conn.close()
            before = path.read_bytes()
            packet = plots.extract_descriptive_series(plots.load_exact_dataset(path, plots.SEPTEMBER_REF))
            self.assertEqual(path.read_bytes(), before)
        ids = {a["id"] for a in packet["agents"]}
        for edge in packet["name_cooccurrence_edges"]:
            self.assertIn(edge["left"], ids); self.assertIn(edge["right"], ids)
            self.assertNotEqual(edge["left"], edge["right"])


if __name__ == "__main__": unittest.main()
