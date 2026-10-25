"""Run conservative local call-graph analysis without external dependencies."""
import sys
from local_code_mind.dead_code import analyze_call_graph
from local_code_mind.cli import main

__all__ = ["analyze_call_graph"]

if __name__ == "__main__":
    raise SystemExit(main(["--dead-code", *sys.argv[1:]]))
