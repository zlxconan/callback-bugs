"""CLI: python -m ops_agent.integrations.timeout_retry_mvp [output-dir]."""

import asyncio
import sys
from pathlib import Path

from .case import TimeoutRetryMvpCase


async def _main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/timeout-retry-mvp")
    outcome = await TimeoutRetryMvpCase(output_dir=output_dir).execute()
    print(outcome.artifacts.case_summary.resolve())


if __name__ == "__main__":
    asyncio.run(_main())
