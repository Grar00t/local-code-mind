"""Offline Hugging Face preparation helper. No upload or network requests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_manifest(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Expected project directory")
    allowed = ["LICENSE", "README.md", "pyproject.toml"]
    files = []
    for name in allowed:
        path = root / name
        if path.is_file() and not path.is_symlink():
            files.append({
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return {
        "format": "local-code-mind-hf-export-v1",
        "mode": "prepare-only",
        "uploads_performed": 0,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print offline HF export manifest (no upload).")
    parser.add_argument("--project", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        data = build_manifest(args.project)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    content = json.dumps(data, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
