"""
Profiler:
- считает метрики по источникам (source_name в node.extra)
- сохраняет JSON-профили в sources_meta/profiles/
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List

from .parser import VPNNode


class Profiler:
    def __init__(self, min_nodes: int = 5, base_dir: str = "sources_meta/profiles"):
        self.min_nodes = min_nodes
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def build_profiles(self, nodes: List[VPNNode]) -> Dict[str, Dict]:
        by_source: Dict[str, List[VPNNode]] = defaultdict(list)

        for n in nodes:
            src = n.extra.get("source_name", "unknown")
            by_source[src].append(n)

        profiles: Dict[str, Dict] = {}

        for source, lst in by_source.items():
            if len(lst) < self.min_nodes:
                # всё равно пишем профиль, но помечаем как weak
                quality_flag = "weak"
            else:
                quality_flag = "ok"

            pings = [n.extra.get("ping") for n in lst if isinstance(n.extra.get("ping"), (int, float))]
            asns = [n.extra.get("asn") for n in lst if isinstance(n.extra.get("asn"), int)]

            profile = {
                "source": source,
                "nodes": len(lst),
                "avg_ping": mean(pings) if pings else None,
                "asn_unique": len(set(asns)) if asns else None,
                "quality": quality_flag,
            }

            profiles[source] = profile

            out_path = self.base_dir / f"{source}.json"
            out_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

        return profiles
