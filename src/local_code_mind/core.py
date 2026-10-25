"""Read-only, bounded AST and Git diagnostics."""
from __future__ import annotations
import ast
import os
import platform
import subprocess
import sys
import tokenize
from pathlib import Path

IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", "build", "dist"}
MAX_SOURCE_BYTES = 512 * 1024


def _git_read(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def _source_paths(root: Path, max_files: int) -> tuple[list[Path], bool]:
    if root.is_file():
        return [root], False
    found = []
    for folder, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".") and not (Path(folder) / name).is_symlink())
        for name in sorted(filenames):
            if not name.lower().endswith(".py"):
                continue
            path = Path(folder) / name
            if path.is_symlink():
                continue
            if len(found) >= max_files:
                return found, True
            found.append(path)
    return found, False


def _branch_score(function: ast.AST) -> int:
    score = 1
    nodes = list(ast.iter_child_nodes(function))
    branches = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.Match, ast.comprehension)
    while nodes:
        node = nodes.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, branches):
            score += 1
        if isinstance(node, ast.BoolOp):
            score += max(0, len(node.values) - 1)
        nodes.extend(ast.iter_child_nodes(node))
    return score


def scan_project(target: str | Path, max_files: int = 500) -> dict:
    if not 1 <= max_files <= 2000:
        raise ValueError("max_files must be between 1 and 2000")
    requested = Path(target).expanduser()
    if requested.is_symlink():
        raise ValueError("symbolic-link target is not allowed")
    root = requested.resolve(strict=True)
    if not root.is_dir() and not (root.is_file() and root.suffix.lower() == ".py"):
        raise ValueError("target must be a directory or a Python file")
    files, truncated = _source_paths(root, max_files)
    git_dir = root if root.is_dir() else root.parent
    result = {
        "target": str(root),
        "python_version": sys.version.split()[0],
        "platform": platform.system() + " " + platform.release(),
        "git_root": _git_read(git_dir, "rev-parse", "--show-toplevel"),
        "git_branch": _git_read(git_dir, "symbolic-ref", "--quiet", "--short", "HEAD"),
        "python_files": len(files),
        "functions": 0,
        "classes": 0,
        "skipped_large_files": 0,
        "parse_errors": [],
        "top_complexity": [],
        "truncated": truncated,
    }
    scores = []
    for file in files:
        relative = file.relative_to(root).as_posix() if root.is_dir() else file.name
        try:
            if file.stat().st_size > MAX_SOURCE_BYTES:
                result["skipped_large_files"] += 1
                continue
            with tokenize.open(file) as stream:
                tree = ast.parse(stream.read(), filename=str(file))
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            result["parse_errors"].append({"file": relative, "reason": type(error).__name__})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result["classes"] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"] += 1
                scores.append({"file": relative, "line": node.lineno, "function": node.name, "branch_score": _branch_score(node)})
    result["top_complexity"] = sorted(scores, key=lambda item: (-item["branch_score"], item["file"], item["line"]))[:5]
    return result
