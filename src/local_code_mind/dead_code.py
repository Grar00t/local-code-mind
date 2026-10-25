"""Conservative, deterministic inter-module AST call graph: candidate findings only."""
from __future__ import annotations

import ast
import tokenize
from pathlib import Path
from .core import _source_paths, MAX_SOURCE_BYTES


def _module_name(relative: str) -> str:
    parts = list(Path(relative).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts.pop(0)  # Conventional src-layout, independent of checkout location.
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__root__"


def _import_base(module: str, is_package: bool, level: int, imported: str | None) -> str:
    if level == 0:
        return imported or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    if level > len(package) + 1:
        return ""  # Invalid relative import; do not manufacture an edge.
    prefix = package[:len(package) - level + 1]
    return ".".join(prefix + ([imported] if imported else []))


def _attribute_path(node: ast.AST) -> list[str] | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return [node.id] + list(reversed(parts))


def _terminal_statements(tree: ast.AST, file: str) -> list[dict]:
    findings = []
    seen = set()
    for parent in ast.walk(tree):
        blocks = [getattr(parent, name, None) for name in ("body", "orelse", "finalbody")]
        if isinstance(parent, ast.Try):
            blocks += [item.body for item in parent.handlers]
        if isinstance(parent, ast.Match):
            blocks += [item.body for item in parent.cases]
        for block in blocks:
            if not isinstance(block, list) or not all(isinstance(item, ast.stmt) for item in block):
                continue
            terminal = False
            for statement in block:
                if terminal and (file, statement.lineno) not in seen:
                    seen.add((file, statement.lineno))
                    findings.append({
                        "file": file, "line": statement.lineno, "confidence": 1.0,
                        "reason": "statement after unconditional return/raise in same suite",
                    })
                if isinstance(statement, (ast.Return, ast.Raise)):
                    terminal = True
    return findings


def _top_imports(tree: ast.Module, module: str, is_package: bool):
    aliases = {}
    declarations = []
    wildcard = False
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                name = alias.asname or alias.name.split(".")[0]
                aliases[name] = alias.name if alias.asname else name
                declarations.append((name, stmt.lineno))
        elif isinstance(stmt, ast.ImportFrom):
            if stmt.module == "__future__":
                continue  # Compiler directives are not unused runtime imports.
            base = _import_base(module, is_package, stmt.level, stmt.module)
            for alias in stmt.names:
                if alias.name == "*":
                    wildcard = True
                    continue
                bound = alias.asname or alias.name
                aliases[bound] = base + "." + alias.name if base else alias.name
                declarations.append((bound, stmt.lineno))
    return aliases, declarations, wildcard


class _Definitions(ast.NodeVisitor):
    def __init__(self, module):
        self.module = module
        self.stack = []
        self.nodes = {}
        self.classes = set()

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.classes.add(".".join([self.module] + self.stack))
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.nodes[".".join([self.module] + self.stack)] = node
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


class _Calls(ast.NodeVisitor):
    def __init__(self, module, symbols, imports, classes):
        self.module = module
        self.symbols = symbols
        self.imports = imports
        self.classes = classes
        self.stack = []
        self.edges = set()
        self.dynamic = False

    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        caller = ".".join([self.module] + self.stack) if self.stack else self.module + ".<module>"
        path = _attribute_path(node.func)
        destination = None
        if path:
            name = path[0]
            if name in ("eval", "exec", "getattr", "globals", "locals", "__import__"):
                self.dynamic = True
            if len(path) == 1:
                for n in range(len(self.stack), -1, -1):
                    option = ".".join([self.module] + self.stack[:n] + [name])
                    if option in self.symbols:
                        destination = option
                        break
                destination = destination or self.imports.get(name)
                if destination is None and self.module + "." + name in self.classes:
                    destination = self.module + "." + name
            elif name in ("self", "cls") and self.stack:
                owner = next(
                    (".".join([self.module] + self.stack[:i + 1])
                     for i in range(len(self.stack) - 1, -1, -1)
                     if ".".join([self.module] + self.stack[:i + 1]) in self.classes),
                    None,
                )
                if owner:
                    destination = ".".join([owner] + path[1:])
            elif name in self.imports:
                destination = ".".join([self.imports[name]] + path[1:])
            else:
                destination = ".".join([self.module] + path)
            if destination in self.classes:
                initializer = destination + ".__init__"
                destination = initializer if initializer in self.symbols else None
        if destination in self.symbols:
            self.edges.add((caller, destination))
        self.generic_visit(node)


def analyze_call_graph(target, max_files=500):
    if not 1 <= max_files <= 2000:
        raise ValueError("max_files must be between 1 and 2000")
    requested = Path(target).expanduser()
    if requested.is_symlink():
        raise ValueError("symlink target is not allowed")
    root = requested.resolve(strict=True)
    if not root.is_dir() and not (root.is_file() and root.suffix.lower() == ".py"):
        raise ValueError("target must be a directory or a Python file")
    files, truncated = _source_paths(root, max_files)
    parsed = {}
    errors = []
    skipped = 0
    for file in files:
        relative = file.relative_to(root).as_posix() if root.is_dir() else file.name
        try:
            if file.stat().st_size > MAX_SOURCE_BYTES:
                skipped += 1
                continue
            with tokenize.open(file) as stream:
                parsed[relative] = ast.parse(stream.read(), filename=relative)
        except (SyntaxError, OSError, ValueError, UnicodeError) as exc:
            errors.append({"file": relative, "reason": type(exc).__name__})

    symbols = {}
    classes = set()
    metadata = {}
    for relative, tree in sorted(parsed.items()):
        module = _module_name(relative)
        definition = _Definitions(module)
        definition.visit(tree)
        symbols.update(definition.nodes)
        classes.update(definition.classes)
        imports, declarations, wildcard = _top_imports(
            tree, module, relative.endswith("/__init__.py"),
        )
        metadata[relative] = (module, imports, declarations, wildcard, tree)

    edges = set()
    dynamic_files = set()
    unused_imports = []
    unreachable = []
    for relative, (module, imports, declarations, wildcard, tree) in sorted(metadata.items()):
        visitor = _Calls(module, symbols, imports, classes)
        visitor.visit(tree)
        edges.update(visitor.edges)
        if visitor.dynamic or wildcard:
            dynamic_files.add(relative)
        loads = {
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        exports = set()
        for statement in tree.body:
            if isinstance(statement, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in statement.targets):
                    if isinstance(statement.value, (ast.List, ast.Tuple)):
                        exports.update(item.value for item in statement.value.elts
                                       if isinstance(item, ast.Constant) and isinstance(item.value, str))
        for name, line in declarations:
            if name not in loads and name not in exports:
                unused_imports.append({
                    "file": relative, "line": line, "name": name, "confidence": 0.8,
                    "reason": "no lexical load or literal __all__ export; may be re-exported dynamically",
                })
        unreachable.extend(_terminal_statements(tree, relative))

    called = {destination for _, destination in edges}
    candidates = []
    for symbol, node in sorted(symbols.items()):
        if symbol in called:
            continue
        file = next((relative for relative, (module, _, _, _, _) in metadata.items()
                     if symbol.startswith(module + ".") and
                     (not any(symbol.startswith(m + ".") and len(m) > len(module)
                              for m, _, _, _, _ in metadata.values()))), "")
        # Module, API and test entrypoints can all be invoked externally.
        method = any(symbol.startswith(cls + ".") for cls in classes)
        confidence = 0.3 if file in dynamic_files else (0.45 if method else 0.55)
        candidates.append({
            "symbol": symbol, "file": file, "line": node.lineno,
            "confidence": confidence,
            "reason": "no statically resolved call; external API or dynamic dispatch remains possible",
        })
    return {
        "definitions": len(symbols),
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
        "dead_candidates": candidates,
        "unreachable": sorted(unreachable, key=lambda item: (item["file"], item["line"])),
        "unused_imports": sorted(unused_imports, key=lambda item: (item["file"], item["line"], item["name"])),
        "dead_code_density": round(len(candidates) / len(symbols), 4) if symbols else 0.0,
        "parse_errors": errors, "skipped_large_files": skipped, "truncated": truncated,
        "limitations": "Static candidate heuristics, not proof of dead code; dynamic dispatch, plugins, callbacks, reflection, and external entrypoints may cause false positives.",
    }
