"""Phase 4: deterministic, offline tests using only Python's standard library."""
from __future__ import annotations
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from local_code_mind.cli import main
from local_code_mind.dead_code import analyze_call_graph
from local_code_mind.exporter import compliance_report, render_html
from local_code_mind.self_heal import run_healing


class Phase4Tests(unittest.TestCase):
    def test_cross_module_call_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("")
            (root / "pkg" / "a.py").write_text("def work():\n    return 42\n")
            (root / "pkg" / "b.py").write_text(
                "from .a import work as fn\ndef caller():\n    return fn()\n"
            )
            graph = analyze_call_graph(root)
            self.assertIn({"from": "pkg.b.caller", "to": "pkg.a.work"}, graph["edges"])
            self.assertNotIn("pkg.a.work", {x["symbol"] for x in graph["dead_candidates"]})

    def test_methods_and_constructor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text(
                "class A:\n"
                "    def __init__(self):\n        self.value = 0\n"
                "    def run(self):\n        self.helper()\n"
                "    def helper(self):\n        return True\n"
                "A()\n", encoding="utf-8"
            )
            graph = analyze_call_graph(root)
            self.assertIn({"from": "a.<module>", "to": "a.A.__init__"}, graph["edges"])
            self.assertIn({"from": "a.A.run", "to": "a.A.helper"}, graph["edges"])

    def test_unused_import_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("import os\nimport sys\nx = os.name\n", encoding="utf-8")
            (root / "b.py").write_text(
                "from a import x\n__all__ = ['x']\n", encoding="utf-8"
            )
            graph = analyze_call_graph(root)
            imports = {(e["file"], e["name"]) for e in graph["unused_imports"]}
            self.assertIn(("a.py", "sys"), imports)
            self.assertNotIn(("a.py", "os"), imports)
            self.assertNotIn(("b.py", "x"), imports)

    def test_unreachable_return_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text(
                "def a():\n    return 1\n    value = 2\n"
                "def b():\n    raise ValueError()\n    value = 2\n", encoding="utf-8"
            )
            graph = analyze_call_graph(root)
            self.assertEqual({item["line"] for item in graph["unreachable"]}, {3, 6})
            self.assertTrue(all(item["confidence"] == 1.0 for item in graph["unreachable"]))

    def test_uncalled_candidates_are_probabilistic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def maybe_external():\n    return 1\n")
            graph = analyze_call_graph(root)
            found = next(item for item in graph["dead_candidates"]
                         if item["symbol"] == "a.maybe_external")
            self.assertLess(found["confidence"], 1.0)
            self.assertEqual(graph["dead_code_density"], 1.0)

    def test_invalid_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                analyze_call_graph(tmp, max_files=0)

    def test_safe_offline_html(self):
        graph = {"dead_candidates": [{"symbol": "<script>alert(1)</script>"}],
                 "unused_imports": [], "unreachable": [], "dead_code_density": 1.0,
                 "truncated": False, "parse_errors": []}
        scan = {"top_complexity": [], "python_files": 1, "functions": 1,
                "truncated": False, "parse_errors": []}
        report = compliance_report(scan, graph)
        rendered = render_html(report, graph)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<script src", rendered)
        self.assertIn("not a third-party certification", report["audit_note"])

    def test_cli_html_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def unused():\n    pass\n", encoding="utf-8")
            report = root / "audit.html"
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                code = main([str(root), "--dead-code", "--html", str(report), "--json"])
            self.assertEqual(code, 0)
            result = json.loads(capture.getvalue())
            self.assertIn("call_graph", result)
            self.assertTrue(report.exists())
            self.assertTrue(report.with_suffix(".json").exists())

    def test_selfheal_pass_no_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_ok.py").write_text(
                "import unittest\nclass TestSmoke(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertEqual(2 + 2, 4)\n"
            )
            output = run_healing(root, max_attempts=2, timeout=10, apply=True)
            self.assertTrue(output["passed"])
            self.assertEqual(len(output["log"]), 1)
            self.assertEqual(output["repairs"], [])

    def test_selfheal_can_fix_local_missing_colon(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "src").mkdir()
            source = root / "src" / "app.py"
            source.write_text("def example()\n    return 1\n", encoding="utf-8")
            test = (
                "import unittest\nfrom pathlib import Path\n"
                "class TestCompile(unittest.TestCase):\n"
                "    def test_source(self):\n"
                "        target = Path(__file__).resolve().parents[1] / 'src' / 'app.py'\n"
                "        compile(target.read_text(encoding='utf-8'), str(target), 'exec')\n"
            )
            (root / "tests" / "test_fix.py").write_text(test, encoding="utf-8")
            report = run_healing(root, max_attempts=3, timeout=10, apply=True)
            self.assertTrue(report["passed"], json.dumps(report))
            self.assertEqual(len(report["log"]), 2)
            self.assertEqual(len(report["repairs"]), 1)
            self.assertIn("def example():", source.read_text(encoding="utf-8"))

    def test_selfheal_unknown_failure_does_not_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            test = "import unittest\nclass Test(unittest.TestCase):\n    def test_bad(self):\n        self.fail('unknown')\n"
            path = root / "tests" / "test_bad.py"
            path.write_text(test, encoding="utf-8")
            report = run_healing(root, max_attempts=2, timeout=10, apply=True)
            self.assertFalse(report["passed"])
            self.assertEqual(path.read_text(encoding="utf-8"), test)
            self.assertEqual(report["repairs"], [])


    def test_standalone_zipapp_works_with_isolated_python(self):
        import subprocess
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from build_zipapp import build
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = Path(__file__).resolve().parents[1]
            bundle = build(project, root / "tool.pyz")
            (root / "sample.py").write_text("def standalone():\n    pass\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(bundle), str(root), "--json"],
                capture_output=True, text=True, timeout=15, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["python_files"], 1)

    def test_rollback_after_nonrepaired_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "src").mkdir()
            source = root / "src" / "app.py"
            original = b"def example()\n    return 1\n"
            source.write_bytes(original)
            (root / "tests" / "test_both.py").write_text(
                "import unittest\nfrom pathlib import Path\n"
                "class Test(unittest.TestCase):\n"
                "    def test_syntax(self):\n"
                "        path = Path(__file__).resolve().parents[1] / 'src' / 'app.py'\n"
                "        compile(path.read_text(), str(path), 'exec')\n"
                "    def test_assertion(self):\n        self.assertEqual(1, 2)\n"
            )
            report = run_healing(root, max_attempts=2, timeout=10, apply=True)
            self.assertFalse(report["passed"])
            self.assertTrue(report["rollback"])
            self.assertEqual(source.read_bytes(), original)

    def test_relative_module_import_is_not_dead(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "src" / "example"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "base.py").write_text("def used():\n    return 1\n")
            (package / "consumer.py").write_text(
                "import example.base as b\ndef use():\n    return b.used()\n"
            )
            graph = analyze_call_graph(root)
            self.assertIn(
                {"from": "example.consumer.use", "to": "example.base.used"},
                graph["edges"]
            )


if __name__ == "__main__":
    unittest.main()
