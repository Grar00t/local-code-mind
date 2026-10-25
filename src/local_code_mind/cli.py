"""CLI output layer: Rich for humans, JSON for independent checks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .core import scan_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="local-code-mind",
        description="Offline, read-only Python AST and Git diagnostics.",
    )
    parser.add_argument("target", nargs="?", default=".", help="Local directory or .py file")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--max-files", type=int, default=500, metavar="N")
    arguments = parser.parse_args(argv)
    try:
        result = scan_project(arguments.target, arguments.max_files)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if arguments.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    console = Console()
    table = Table(title="local-code-mind | local repository diagnostics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", overflow="fold")
    for name in (
        "target", "python_version", "platform", "git_root", "git_branch",
        "python_files", "functions", "classes", "skipped_large_files", "truncated",
    ):
        table.add_row(name.replace("_", " "), str(result[name]))
    table.add_row("parse errors", str(len(result["parse_errors"])))
    console.print(table)

    if result["top_complexity"]:
        scores = Table(title="Top AST branch scores (heuristic)")
        scores.add_column("File")
        scores.add_column("Function")
        scores.add_column("Line", justify="right")
        scores.add_column("Score", justify="right")
        for item in result["top_complexity"]:
            scores.add_row(
                item["file"], item["function"],
                str(item["line"]), str(item["branch_score"]),
            )
        console.print(scores)
    if result["parse_errors"]:
        console.print("[yellow]Parse errors (filenames only):[/yellow]")
        for item in result["parse_errors"]:
            console.print(f"  {item['file']}: {item['reason']}")
    if result["truncated"]:
        console.print("[yellow]File limit reached; scan is incomplete.[/yellow]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
