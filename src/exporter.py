"""Offline HTML and JSON compliance exporter."""
from local_code_mind.exporter import compliance_report, render_html, write_reports
from local_code_mind.cli import main

__all__ = ["compliance_report", "render_html", "write_reports"]

if __name__ == "__main__":
    raise SystemExit(main())
