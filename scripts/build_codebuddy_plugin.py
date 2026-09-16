#!/usr/bin/env python3
"""Build the CodeBuddy plugin Skill payload from canonical Built-in Skills."""

import argparse
from pathlib import Path

from ops_agent.skills import SkillCatalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = PROJECT_ROOT / "skills" / "builtin"
PLUGIN_SKILLS_ROOT = PROJECT_ROOT / "integrations" / "codebuddy" / "ops-agent-plugin" / "skills"


def sync(*, check: bool) -> None:
    skills = SkillCatalog(CANONICAL_ROOT).load_all()
    expected_names = {skill.name for skill in skills}
    existing_names = (
        {path.name for path in PLUGIN_SKILLS_ROOT.iterdir() if path.is_dir()}
        if PLUGIN_SKILLS_ROOT.is_dir()
        else set()
    )
    unexpected = existing_names - expected_names
    if unexpected:
        raise RuntimeError(
            f"Unexpected generated CodeBuddy Skill directories: {sorted(unexpected)}"
        )

    stale: list[Path] = []
    for skill in skills:
        output = PLUGIN_SKILLS_ROOT / skill.name / "SKILL.md"
        if not output.is_file() or output.read_text(encoding="utf-8") != skill.instructions:
            stale.append(output)
            if not check:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(skill.instructions, encoding="utf-8")

    if check and stale:
        rendered = ", ".join(str(path.relative_to(PROJECT_ROOT)) for path in stale)
        raise RuntimeError(f"CodeBuddy generated Skills are stale or missing: {rendered}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated Skill files differ; do not write files.",
    )
    args = parser.parse_args()
    sync(check=args.check)


if __name__ == "__main__":
    main()
