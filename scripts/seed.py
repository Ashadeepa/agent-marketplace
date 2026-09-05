"""Validate and load data/agents/*.json into the registry, printing a summary.

Run this standalone to sanity-check manifests before starting the server:
    python scripts/seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.registry import registry  # noqa: E402
from app.versioning import compute_behavior_hash  # noqa: E402


def main() -> None:
    registry.load_from_disk()
    agents = registry.all_latest()
    print(f"Loaded {len(agents)} agent(s):\n")
    for m in sorted(agents, key=lambda a: a.agent_id):
        versions = registry.get_all_versions(m.agent_id)
        print(f"  {m.agent_id}")
        print(f"    latest version : {m.version}  (behavior_hash={compute_behavior_hash(m)})")
        print(f"    publisher      : {m.publisher.name} ({m.publisher.team}), verified={m.publisher.verified}")
        print(f"    review status  : {m.review.status.value}")
        print(f"    versions on file: {[v.version for v in versions]}")
        print()


if __name__ == "__main__":
    main()
