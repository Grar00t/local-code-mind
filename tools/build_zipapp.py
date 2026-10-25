"""Build a standalone Python zipapp without pip, PyPI, or network access."""
from __future__ import annotations
import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path


def build(project: Path, output: Path) -> Path:
    package = (project / "src" / "local_code_mind").resolve(strict=True)
    if not package.is_dir() or not (package / "cli.py").is_file():
        raise ValueError("Expected local_code_mind source package")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lcm-zipapp-") as scratch:
        root = Path(scratch)
        shutil.copytree(package, root / "local_code_mind",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (root / "__main__.py").write_text(
            "from local_code_mind.cli import main\nraise SystemExit(main())\n",
            encoding="utf-8",
        )
        zipapp.create_archive(root, target=output, interpreter="/usr/bin/env python3",
                              compressed=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Create offline standalone .pyz")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist/local-code-mind.pyz"))
    args = parser.parse_args()
    print(build(args.project, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
