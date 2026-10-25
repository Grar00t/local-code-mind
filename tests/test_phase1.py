"""Phase 1 regression tests: stdlib unittest only (safe under python -I -S)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from local_code_mind.cli import main
from local_code_mind.core import scan_project


class Phase1Tests(unittest.TestCase):
    def test_ast_counts_and_branch_score(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "a.py").write_text(
                "class C:\n    def f(self, x):\n        if x and x > 1:\n            return 1\n        return 0\n", encoding="utf-8"
            )
            result = scan_project(root)
            self.assertEqual(result["python_files"], 1)
            self.assertEqual(result["classes"], 1)
            self.assertEqual(result["functions"], 1)
            self.assertEqual(result["top_complexity"][0]["branch_score"], 3)
            self.assertEqual(result["parse_errors"], [])

    def test_syntax_errors_are_reported_without_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "broken.py").write_text("def nope(:\n", encoding="utf-8")
            (root / "never_execute.py").write_text(
                "raise RuntimeError('MUST NOT EXECUTE')\n", encoding="utf-8"
            )
            result = scan_project(root)
            self.assertEqual(len(result["parse_errors"]), 1)
            self.assertEqual(result["parse_errors"][0]["reason"], "SyntaxError")

    def test_ignored_dirs_and_file_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ignored = root / ".venv"
            ignored.mkdir()
            (ignored / "ignore.py").write_text("def ignored(): pass\n", encoding="utf-8")
            for name in ("a.py", "b.py", "c.py"):
                (root / name).write_text("pass\n", encoding="utf-8")
            result = scan_project(root, max_files=2)
            self.assertEqual(result["python_files"], 2)
            self.assertTrue(result["truncated"])

    def test_invalid_target_and_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises((ValueError, FileNotFoundError)):
                scan_project(root / "missing")
            with self.assertRaises(ValueError):
                scan_project(root, max_files=0)
            with self.assertRaises(ValueError):
                scan_project(root, max_files=2001)

    def test_single_file_and_json_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "single.py"
            file.write_text("def hello():\n    return 1\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([str(file), "--json"]), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["python_files"], 1)
            self.assertEqual(result["functions"], 1)

    def test_cli_bad_target(self):
        with tempfile.TemporaryDirectory() as folder:
            output = StringIO()
            with redirect_stderr(output):
                self.assertEqual(main([str(Path(folder) / "missing"), "--json"]), 2)
            self.assertIn("error:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
