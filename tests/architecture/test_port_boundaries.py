import ast
from pathlib import Path

PORTS_ROOT = Path(__file__).parents[2] / "src" / "ops_agent" / "ports"


def test_shared_ports_only_import_contracts_and_standard_library() -> None:
    violations: list[str] = []
    for path in PORTS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            root = node.module.split(".", maxsplit=1)[0]
            allowed_packages = ("ops_agent.contracts", "ops_agent.ports")
            if root == "ops_agent" and not node.module.startswith(allowed_packages):
                violations.append(f"{path}: forbidden import {node.module}")
            if root in {"fastapi", "langchain"}:
                violations.append(f"{path}: framework import {node.module}")

    assert violations == []


def test_engine_port_packages_do_not_define_competing_protocols() -> None:
    package_root = PORTS_ROOT.parent
    for engine in ("knowledge", "reasoning", "investigation", "reproduction"):
        engine_ports = package_root / engine / "ports"
        for path in engine_ports.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            protocol_classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            assert protocol_classes == []
