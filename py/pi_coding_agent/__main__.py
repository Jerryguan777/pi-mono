"""Allow running as: python -m pi_coding_agent."""

from __future__ import annotations

import asyncio
import sys

from pi_coding_agent.main import main

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
