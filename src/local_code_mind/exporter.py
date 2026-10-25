"""Single-file, offline, escaped HTML and JSON compliance reports."""
from __future__ import annotations
import html
import json
from pathlib import Path


def compliance_report(scan, graph):
    scores = [row["branch_score"] for row in scan["top_complexity"]]
    return {
        "schema": "local-code-mind-compliance-v1",
        "offline_runtime": True,
        "stdlib_runtime": True,
        "source_execution": False,
        "network_calls": False,
        "python_files": scan["python_files"],
        "functions": scan["functions"],
        "dead_code_density": graph["dead_code_density"],
        "uncalled_candidates": len(graph["dead_candidates"]),
        "unreachable_statements": len(graph["unreachable"]),
        "unused_imports": len(graph["unused_imports"]),
        "highest_branch_score": max(scores, default=0),
        "branch_score_kind": "heuristic, not full McCabe cyclomatic complexity",
        "complete": not (scan["truncated"] or graph["truncated"] or scan["parse_errors"] or graph["parse_errors"]),
        "readiness": "review_required" if (scan["truncated"] or graph["truncated"] or scan["parse_errors"] or graph["parse_errors"]) else "offline_capable_not_certified",
        "audit_note": "Self-declared technical properties; not a third-party certification or security guarantee.",
    }


def render_html(report, graph):
    safe = lambda value: html.escape(str(value), quote=True)
    rows = "".join(
        "<tr><th>" + safe(key) + "</th><td>" + safe(value) + "</td></tr>"
        for key, value in sorted(report.items())
    )
    sections = []
    for key in ("dead_candidates", "unreachable", "unused_imports"):
        items = graph[key]
        content = "".join("<li><code>" + safe(json.dumps(item, ensure_ascii=False, sort_keys=True)) + "</code></li>" for item in items)
        sections.append("<h2>" + safe(key.replace("_", " ")) + "</h2><ol>" + content + "</ol>")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>local-code-mind | Offline Compliance</title>"
        "<style>body{font:16px system-ui,Arial;max-width:1000px;margin:2rem auto;padding:0 1rem;"
        "color:#17212b;background:#fafafa}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #aab;padding:.55rem;text-align:left;overflow-wrap:anywhere}"
        "th{width:35%;background:#e8eef2}li{margin:.5rem 0;overflow-wrap:anywhere}"
        "code{white-space:pre-wrap}</style></head><body>"
        "<h1>Local Code Mind — Offline Compliance Report</h1>"
        "<p>Static evidence only. Not a formal compliance certification.</p>"
        "<table>" + rows + "</table>" + "".join(sections) + "</body></html>"
    )


def write_reports(target, scan, graph):
    """Write only explicit output paths; no remote resources or scripts."""
    target = Path(target)
    report = compliance_report(scan, graph)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(report, graph), encoding="utf-8")
    json_path = target.with_suffix(".json")
    json_path.write_text(json.dumps({"compliance": report, "analysis": graph}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, json_path
