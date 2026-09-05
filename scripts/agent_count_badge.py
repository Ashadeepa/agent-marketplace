"""
Regenerates badges/agents-count.json — a shields.io "endpoint" badge data file — from the current
contents of data/agents/*.json. Run by .github/workflows/agents-badge.yml on every push that
touches data/agents/, so the README badge never drifts from the actual registry.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "agents"
BADGE_PATH = Path(__file__).resolve().parent.parent / "badges" / "agents-count.json"


def count_agents() -> int:
    return sum(1 for _ in DATA_DIR.glob("*.json"))


def main() -> None:
    count = count_agents()
    BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BADGE_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "label": "agents",
                "message": str(count),
                "color": "blue",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"{BADGE_PATH}: {count} agent(s)")


if __name__ == "__main__":
    main()
