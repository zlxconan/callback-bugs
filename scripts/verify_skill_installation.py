#!/usr/bin/env python3
"""Verify a mounted Product Skill repository before application startup."""

import argparse
import asyncio
import json
import sys

from ops_agent.skill_runtime import SkillInstallationConfig, verify_skill_installation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True, help="Exact manifest product value")
    parser.add_argument("--version", required=True, help="Primary product version")
    parser.add_argument(
        "--comparison-version",
        required=True,
        help="Second installed version used to prove version isolation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = asyncio.run(
            verify_skill_installation(
                SkillInstallationConfig.from_env(),
                product=args.product,
                product_version=args.version,
                comparison_version=args.comparison_version,
            )
        )
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
