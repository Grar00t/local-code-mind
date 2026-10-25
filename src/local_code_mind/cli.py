"""Zero-dependency CLI; JSON, call graph and standalone offline reports."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .core import scan_project
from .dead_code import analyze_call_graph
from .exporter import write_reports, compliance_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="local-code-mind", description="Offline stdlib AST analysis")
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--dead-code", action="store_true", help="Include conservative static call graph")
    parser.add_argument("--html", type=Path, metavar="FILE", help="Export standalone HTML and adjacent JSON")
    args = parser.parse_args(argv)
    try:
        scan = scan_project(args.target, args.max_files)
        graph = analyze_call_graph(args.target, args.max_files) if args.dead_code or args.html else None
        if args.html:
            paths = write_reports(args.html, scan, graph)
        else:
            paths = None
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        output = {"scan": scan, "call_graph": graph, "compliance": compliance_report(scan, graph)} if graph else scan
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    print("local-code-mind | sovereign offline diagnostics")
    for key in ("target", "python_version", "platform", "git_root", "git_branch", "python_files",
                "functions", "classes", "skipped_large_files", "truncated"):
        print(f"{key:22} {scan[key]}")
    print(f"{'parse_errors':22} {len(scan['parse_errors'])}")
    print("Top branch scores (heuristic):")
    for item in scan["top_complexity"]:
        print(f"  {item['branch_score']:3} {item['file']}:{item['line']} {item['function']}")
    if graph:
        print("Call graph:", len(graph["edges"]), "edges,", len(graph["dead_candidates"]), "uncalled candidates")
        print("Unreachable:", len(graph["unreachable"]), "Unused imports:", len(graph["unused_imports"]))
        for item in graph["dead_candidates"][:15]:
            print("  candidate", item["symbol"], "confidence", item["confidence"])
    if paths:
        print("Exported:", paths[0], paths[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
