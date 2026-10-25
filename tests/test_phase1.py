"""Phase 1 offline scanner tests: no network or repository execution."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_code_mind.cli import main
from local_code_mind.core import scan_project


def test_ast_counts_and_branch_score(tmp_path: Path):
    (tmp_path / "a.py").write_text(
        "class C:\n    def f(self, x):\n        if x and x > 1:\n            return 1\n        return 0\n",
        encoding="utf-8",
    )
    result = scan_project(tmp_path)
    assert result["python_files"] == 1
    assert result["classes"] == 1
    assert result["functions"] == 1
    assert result["top_complexity"][0]["branch_score"] == 3
    assert not result["parse_errors"]


def test_syntax_errors_are_reported_without_execution(tmp_path: Path):
    (tmp_path / "broken.py").write_text("def nope(:\n", encoding="utf-8")
    (tmp_path / "never_execute.py").write_text(
        "raise RuntimeError('MUST NOT EXECUTE')\n", encoding="utf-8"
    )
    result = scan_project(tmp_path)
    assert len(result["parse_errors"]) == 1
    assert result["parse_errors"][0]["reason"] == "SyntaxError"


def test_ignored_dirs_and_file_limit(tmp_path: Path):
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "ignore.py").write_text("def ignored(): pass\n")
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("pass\n")
    result = scan_project(tmp_path, max_files=2)
    assert result["python_files"] == 2
    assert result["truncated"] is True


def test_invalid_target_and_limits(tmp_path: Path):
    with pytest.raises((ValueError, FileNotFoundError)):
        scan_project(tmp_path / "missing")
    with pytest.raises(ValueError):
        scan_project(tmp_path, max_files=0)
    with pytest.raises(ValueError):
        scan_project(tmp_path, max_files=2001)


def test_single_file_and_json_cli(tmp_path: Path, capsys):
    file = tmp_path / "single.py"
    file.write_text("def hello():\n    return 1\n", encoding="utf-8")
    assert main([str(file), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["python_files"] == 1
    assert result["functions"] == 1


def test_cli_bad_target(tmp_path: Path, capsys):
    assert main([str(tmp_path / "missing"), "--json"]) == 2
    assert "error:" in capsys.readouterr().err
