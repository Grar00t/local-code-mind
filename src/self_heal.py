"""Run the bounded self-healing harness on an explicitly selected local project."""
from local_code_mind.self_heal import main, run_healing

__all__ = ["main", "run_healing"]

if __name__ == "__main__":
    raise SystemExit(main())
