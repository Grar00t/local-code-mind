# local-code-mind

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License: MIT](https://img.shields.io/badge/License-MIT-green) ![Release](https://img.shields.io/badge/release-v1.1.0--sovereign-blueviolet) ![CI](https://img.shields.io/badge/CI-local%20tests%20only-informational)

**Local-first, offline and read-only Python AST analyzer.** It summarizes a local repository's Python files, classes, functions, Git status context, and an explicit AST *branch-score heuristic*. It does not run the analyzed source, use hosted AI, or make network calls during scans.

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/Grar00t/local-code-mind.git
cd local-code-mind
python -S src/main.py . --dead-code
python -S src/main.py . --json
python -S tools/build_zipapp.py
python -I -S dist/local-code-mind.pyz . --dead-code --html reports/audit.html
```

To run directly from the checkout without installing any package:

```powershell
python src/main.py .
python src/main.py "D:\\projects\\other-repo" --max-files 100
```

On Linux/macOS replace `python` with `python3` if needed. The tool is compatible with Python 3.10+. The core runtime has zero third-party dependencies. Source and zipapp execution need only Python. Optional `pip install -e .` uses a packaging backend and may fetch build tools, so it is not part of the air-gapped procedure.

## Output preview

Plain-text CLI output (illustrative; values depend on the scanned directory):

```text
local-code-mind | sovereign offline diagnostics
python_version         3.11.9
python_files           16
functions              49
classes                4
parse_errors           0
Call graph: 51 edges, 25 uncalled candidates
Unreachable: 0 Unused imports: 1
```

For machine-readable export:

```powershell
local-code-mind . --json > report.json
```

```json
{
  "target": "D:\\\\projects\\\\local-code-mind",
  "python_files": 5,
  "functions": 11,
  "classes": 0,
  "parse_errors": [],
  "truncated": false
}
```

The JSON preview shows selected keys; actual output includes platform, Git context, file limits and top AST branch scores.

## What is measured

- Recursively count `.py` files, functions and classes without importing project code.
- Rank functions using a **branch-score heuristic**, not full McCabe cyclomatic complexity; nested functions are evaluated separately.
- Detect syntax/encoding failures, show Git repository root/branch when available, and produce deterministic JSON.
- Default limit: 500 Python files (configurable with `--max-files N`, 1–2000); skip files larger than 512 KiB, symlinked files and common generated folders.
- Report skipped files and truncated scans. This is **not** a malware sandbox, security scanner, multi-language analyzer or full repository history index.

## Testing

```powershell
python -I -S -m unittest discover -s tests -v
python -S tools/demo_self_heal.py
```

Twenty offline unit tests cover AST counts, cross-module calls, conservative dead-code candidates, unreachable branches, unused imports, safe HTML, rollback, and standalone zipapp operation. Tests run locally; **no GitHub Actions workflows** are bundled.

## Self-healing limitations

The optional harness repairs missing colons only, after an explicit `--apply`. It retries locally and rolls back an unsuccessful change. Other bugs require manual review; never execute untrusted test suites.

## Release & license

- v1.0.0: first verified local CLI release.
- v1.1.0-sovereign: standard-library-only runtime, call-graph candidates, offline HTML/JSON exporter, bounded self-healing harness.
- MIT License, see [LICENSE](LICENSE).
- No model weights or datasets are included. Hugging Face export/sync is optional and is not part of the local scan.
