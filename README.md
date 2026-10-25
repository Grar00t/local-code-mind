# local-code-mind

![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Offline](https://img.shields.io/badge/runtime-offline-informational)
![Tests](https://img.shields.io/badge/local%20tests-6%20passed-success)

**Local-first, read-only Python AST inspection and Git diagnostics.** The CLI never imports or executes inspected source files and does not require a model, GPU, API key, paid service, or network connection at runtime.

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/Grar00t/local-code-mind.git
cd local-code-mind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
local-code-mind .
local-code-mind . --json
python -m pytest -q
```

On Linux/macOS activate with `source .venv/bin/activate`. Installation of dependencies may require internet access once; **scanning itself does not**.

For a source checkout on a machine with Rich installed, run without installation:

```powershell
python src/main.py "D:\path\to\another\repository"
python src/main.py . --json --max-files 100
```

## Example Rich terminal output

```text
local-code-mind | local repository diagnostics
Metric              Value
target              D:\projects\local-code-mind
python version      3.11.9
git root            None
python files        5
functions           11
classes             0
parse errors        0

Top AST branch scores (heuristic)
File                        Function      Score
src/local_code_mind/core.py scan_project  14
src/local_code_mind/core.py _source_paths 10
```

The example above reflects the **pre-publication local scan**; counts may change after adding files.

## JSON export

```powershell
local-code-mind . --json > scan.json
```

Example excerpt (paths and counts depend on your repository):

```json
{
  "python_version": "3.11.9",
  "python_files": 5,
  "functions": 11,
  "classes": 0,
  "parse_errors": [],
  "top_complexity": [
    {
      "file": "src/local_code_mind/core.py",
      "function": "scan_project",
      "branch_score": 14
    }
  ]
}
```

## What it measures

- Counts Python files, function definitions and class definitions using Python's `ast` module.
- Ranks five functions by a **branch-score heuristic**, not an exact McCabe cyclomatic complexity metric.
- Reports local Git root and branch using read-only Git commands.
- Reports syntax failures without executing the affected code.
- Skips typical generated directories, symbolic links, and files above 512 KiB.
- Limits scans to 500 Python files by default; `--max-files` supports 1 through 2000.

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m compileall -q src tests hf_export.py
python hf_export.py
```

The initial local phase passed **6/6 tests**. Release tests should be rerun after documentation and packaging changes. No GitHub Actions workflows are included.

## Hugging Face preparation

`python hf_export.py` prints a local SHA-256 manifest of selected documentation/metadata files. It performs **no uploads**, model synchronization, authentication, or API calls. It is not a trained model and is not a Hub publisher.

## Security and limitations

This is a static analysis aid, **not** a malware scanner or sandbox. Do not assume arbitrary repositories are safe to run or install. The tool reads files within the selected directory; treat JSON output as potentially sensitive if file paths are confidential. It does not guarantee full traversal in inaccessible directories or exact code complexity measurements.

## License

MIT — see [LICENSE](LICENSE).
