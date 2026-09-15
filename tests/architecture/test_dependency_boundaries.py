import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "ops_agent"
ENGINE_NAMES = {"knowledge", "reasoning", "investigation", "reproduction"}
AI_BOUNDARIES = {"adapters", "integrations"}
RUNTIME_ROOT = PACKAGE_ROOT / "core" / "runtime"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_framework_imports_stay_at_architectural_boundaries() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        relative_parts = path.relative_to(PACKAGE_ROOT).parts
        imports = _imports_in(path)
        for imported in imports:
            if imported == "fastapi" or imported.startswith("fastapi."):
                if not relative_parts or relative_parts[0] != "api":
                    violations.append(f"{path}: FastAPI import outside api")
            if imported == "langchain" or imported.startswith("langchain."):
                if not AI_BOUNDARIES.intersection(relative_parts):
                    violations.append(f"{path}: LangChain import outside adapters/integrations")

    assert violations == []


def test_engines_do_not_import_other_engine_implementations() -> None:
    violations: list[str] = []
    for engine in ENGINE_NAMES:
        engine_root = PACKAGE_ROOT / engine
        for path in engine_root.rglob("*.py"):
            imports = _imports_in(path)
            for other_engine in ENGINE_NAMES - {engine}:
                forbidden_prefix = f"ops_agent.{other_engine}"
                if any(
                    imported == forbidden_prefix or imported.startswith(f"{forbidden_prefix}.")
                    for imported in imports
                ):
                    violations.append(f"{path}: imports {other_engine} implementation")

    assert violations == []


def test_core_runtime_has_only_deterministic_dependencies() -> None:
    allowed_internal = ("ops_agent.contracts", "ops_agent.ports", "ops_agent.core.runtime")
    forbidden_names = {"langchain", "openai", "qwen", "glm", "codex", "codebuddy"}
    violations: list[str] = []

    for path in RUNTIME_ROOT.rglob("*.py"):
        for imported in _imports_in(path):
            normalized = imported.lower()
            if any(name in normalized.split(".") for name in forbidden_names):
                violations.append(f"{path}: forbidden runtime dependency {imported}")
            if imported.startswith("ops_agent.") and not imported.startswith(allowed_internal):
                violations.append(f"{path}: runtime bypasses contracts/ports via {imported}")

    assert violations == []
