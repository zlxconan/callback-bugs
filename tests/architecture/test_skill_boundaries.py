import ast
from pathlib import Path

from ops_agent.skill_runtime import SkillType

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "ops_agent"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_core_has_no_product_plugin_or_crawler_dependency() -> None:
    imports = {
        imported
        for path in (PACKAGE_ROOT / "core").rglob("*.py")
        for imported in imported_modules(path)
    }

    assert not any("product_skill" in imported for imported in imports)
    assert not any("crawler" in imported for imported in imports)
    assert not any(imported.startswith("ops_agent.skill_runtime") for imported in imports)


def test_knowledge_has_no_playwright_or_crawler_dependency() -> None:
    imports = {
        imported
        for path in (PACKAGE_ROOT / "knowledge").rglob("*.py")
        for imported in imported_modules(path)
    }

    assert not any(imported.startswith("playwright") for imported in imports)
    assert not any("crawler" in imported for imported in imports)


def test_contracts_and_core_have_no_langchain_dependency() -> None:
    imports = {
        imported
        for root in (PACKAGE_ROOT / "contracts", PACKAGE_ROOT / "core")
        for path in root.rglob("*.py")
        for imported in imported_modules(path)
    }

    assert not any(imported.startswith("langchain") for imported in imports)


def test_runtime_and_reasoning_do_not_read_product_plugin_files() -> None:
    for root in (PACKAGE_ROOT / "core", PACKAGE_ROOT / "reasoning"):
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "product-skills" not in source
            assert "SkillLoader(" not in source


def test_tool_skills_are_not_incident_runtime_skill_types() -> None:
    assert {item.value for item in SkillType} == {
        "BUILTIN_METHOD",
        "PRODUCT",
        "TROUBLESHOOTING",
    }
