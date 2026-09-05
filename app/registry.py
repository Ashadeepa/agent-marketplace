"""
In-memory registry, seeded from data/agents/*.json.

Each JSON file is a list of manifest versions for a single agent_id, oldest first. The registry
keeps the full version history (needed for versioning diffs) and exposes the latest version as
the default for discovery/install.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.models import AgentManifest

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "agents"


class Registry:
    def __init__(self) -> None:
        # agent_id -> list of AgentManifest, sorted oldest -> newest
        self._versions: dict[str, list[AgentManifest]] = {}

    def load_from_disk(self, data_dir: Path = DATA_DIR) -> None:
        self._versions.clear()
        for path in sorted(data_dir.glob("*.json")):
            raw = json.loads(path.read_text())
            manifests = [AgentManifest.model_validate(v) for v in raw]
            if not manifests:
                continue
            agent_id = manifests[0].agent_id
            manifests.sort(key=lambda m: _version_key(m.version))
            self._versions[agent_id] = manifests

    def all_latest(self) -> list[AgentManifest]:
        return [versions[-1] for versions in self._versions.values()]

    def get_latest(self, agent_id: str) -> AgentManifest | None:
        versions = self._versions.get(agent_id)
        return versions[-1] if versions else None

    def get_version(self, agent_id: str, version: str) -> AgentManifest | None:
        for m in self._versions.get(agent_id, []):
            if m.version == version:
                return m
        return None

    def get_all_versions(self, agent_id: str) -> list[AgentManifest]:
        return list(self._versions.get(agent_id, []))

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._versions


def _version_key(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return (0,)


registry = Registry()
