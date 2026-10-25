"""Bounded local test-repair loop: syntax-colon repair only, backed up and rolled back."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')
COLON_LINE = re.compile(r'^([ \t]*(?:async[ \t]+def|def|if|elif|else|for|async[ \t]+for|while|try|except|finally|with|async[ \t]+with|class)\b[^#\r\n]*)$')


def _test(root, timeout):
    try:
        return subprocess.run(
            [sys.executable, "-I", "-S", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=root, capture_output=True, text=True, timeout=timeout, check=False,
            env=None,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess([], 124, stdout="", stderr="test_timeout: " + str(exc))


def _repair_colon(root, traceback):
    """Repair a missing trailing colon ONLY when the traceback identifies SyntaxError."""
    if "SyntaxError: expected ':'" not in traceback and "SyntaxError: invalid syntax" not in traceback:
        return None
    for filename, number in reversed(FILE_LINE.findall(traceback)):
        path = Path(filename)
        if not path.is_absolute():
            path = root / path
        try:
            path = path.resolve(strict=True)
            path.relative_to((root / "src").resolve(strict=True))
        except (OSError, ValueError):
            continue
        if path.suffix != ".py" or path.is_symlink():
            continue
        original = path.read_bytes()
        try:
            text = original.decode("utf-8")
        except UnicodeError:
            continue
        lines = text.splitlines(keepends=True)
        index = int(number) - 1
        if not 0 <= index < len(lines):
            continue
        line = lines[index]
        body = line.rstrip("\r\n")
        if body.rstrip().endswith(":") or not COLON_LINE.fullmatch(body):
            continue
        # Only modify the reported line; preserve existing newline style.
        ending = line[len(body):]
        lines[index] = body.rstrip() + ":" + ending
        updated = "".join(lines)
        try:
            compile(updated, str(path), "exec")
        except SyntaxError:
            continue
        path.write_bytes(updated.encode("utf-8"))
        return path, original, int(number)
    return None


def run_healing(root, max_attempts=3, timeout=30, apply=False):
    """Never changes tests. On failed repair, restores source bytes exactly."""
    root = Path(root).resolve(strict=True)
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be 1..5")
    log = []
    repairs = []
    for attempt in range(1, max_attempts + 1):
        result = _test(root, timeout)
        trace = result.stdout + "\n" + result.stderr
        location = FILE_LINE.findall(trace)
        entry = {"attempt": attempt, "exit_code": result.returncode,
                 "traceback_location": {"file": location[-1][0], "line": int(location[-1][1])} if location else None,
                 "stderr_tail": result.stderr[-1000:]}
        log.append(entry)
        if result.returncode == 0:
            return {"passed": True, "log": log, "repairs": [{"file": str(p), "line": n} for p, _, n in repairs], "rollback": False}
        if not apply or attempt == max_attempts:
            break
        repair = _repair_colon(root, trace)
        if repair is None:
            entry["repair"] = "none: unsupported failure; no speculative source edits"
            break
        repairs.append(repair)
        entry["repair"] = "missing colon at " + str(repair[0]) + ":" + str(repair[2])
    for path, original, _ in reversed(repairs):
        path.write_bytes(original)
    return {"passed": False, "log": log, "repairs": [], "rollback": bool(repairs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded stdlib unittest recovery (no arbitrary code generation).")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--apply", action="store_true", help="Allow only guarded missing-colon fixes in src/")
    args = parser.parse_args(argv)
    result = run_healing(args.project, args.max_attempts, args.timeout, args.apply)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
