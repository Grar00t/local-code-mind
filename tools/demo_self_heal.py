"""Safely demonstrate self-healing on a disposable synthetic project."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from local_code_mind.self_heal import run_healing


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lcm-heal-demo-") as scratch:
        project = Path(scratch)
        (project / "src").mkdir()
        (project / "tests").mkdir()
        source = project / "src" / "example.py"
        source.write_text("def example()\n    return 1\n", encoding="utf-8")
        (project / "tests" / "test_compile.py").write_text(
            "from pathlib import Path\nimport unittest\n"
            "class TestCompile(unittest.TestCase):\n"
            "    def test_source(self):\n"
            "        path = Path(__file__).resolve().parents[1] / 'src' / 'example.py'\n"
            "        compile(path.read_text(encoding='utf-8'), str(path), 'exec')\n",
            encoding="utf-8",
        )
        result = run_healing(project, max_attempts=3, timeout=15, apply=True)
        result["repaired_source_confirmed"] = "def example():" in source.read_text(encoding="utf-8")
        result["disposable_fixture"] = True
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["passed"] and len(result["log"]) == 2 and result["repaired_source_confirmed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
