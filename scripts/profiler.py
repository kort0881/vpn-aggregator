"""
Profiler:
- считает метрики по источникам (source_name в node.extra)
- сохраняет JSON-профили в sources_meta/profiles/

Структура профиля:
{
  "id": str,
  "total_nodes": int,
  "unique_ips": int,
  "asn_stats": {asn: count},
  "country_stats": {country: count},
  "eu_share": float,
  "bad_country_share": float,
  "avg_ping": int|None,
  "alive_ratio": float|None,
  "last_seen": ISO8601
}
"""

from __future__ import annotations

import json
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List

from .parser import VPNNode


class Profiler:
    def __init__(
        self,
        min_nodes: int = 5,
        base_dir: str = "sources_meta/profiles",
        config: Dict | None = None,
    ):
        self.min_nodes = min_nodes
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.config = config or {}
        geo_cfg = (self.config.get("filters") or {}).get("geo") or {}
        self.exclude_countries = set(geo_cfg.get("exclude_countries", []) or [])

        # тот же набор EU-стран, что и в фильтре
        self.eu_countries = {
            "DE", "NL", "FR", "PL", "SE", "FI", "IT", "ES", "CZ", "AT", "BE",
            "DK", "IE", "PT", "RO", "BG", "SK", "SI", "GR", "HU", "HR", "EE",
            "LV", "LT", "LU", "CY", "MT"
        }

    def build_profiles(self, nodes: List[VPNNode]) -> Dict[str, Dict]:
        by_source: Dict[str, List[VPNNode]] = defaultdict(list)

        for n in nodes:
            src = n.extra.get("source_name", "unknown")
            by_source[src].append(n)

        profiles: Dict[str, Dict] = {}
        ts = datetime.now(timezone.utc).isoformat()

        for source, lst in by_source.items():
            # базовые коллекции
            ips = [n.extra.get("ip") for n in lst if n.extra.get("ip")]
            countries = [n.extra.get("country") for n in lst if n.extra.get("country")]
            asns = [n.extra.get("asn") for n in lst if n.extra.get("asn")]

            pings = [
                n.extra.get("ping")
                for n in lst
                if isinstance(n.extra.get("ping"), (int, float))
            ]
            alive_flags = [
                n.extra.get("alive")
                for n in lst
                if isinstance(n.extra.get("alive"), bool)
            ]

            total_nodes = len(lst)
            unique_ips = len(set(ips))

            asn_stats = dict(Counter(asns))
            country_stats = dict(Counter(countries))

            total_with_country = sum(country_stats.values()) or 1

            eu_count = sum(
                country_stats.get(c, 0) for c in self.eu_countries
            )
            eu_share = eu_count / total_with_country

            bad_count = sum(
                country_stats.get(c, 0) for c in self.exclude_countries
            )
            bad_country_share = bad_count / total_with_country

            avg_ping = int(mean(pings)) if pings else None
            alive_ratio = (
                sum(1 for a in alive_flags if a) / len(alive_flags)
                if alive_flags
                else None
            )

            profile = {
                "id": source,
                "total_nodes": total_nodes,
                "unique_ips": unique_ips,
                "asn_stats": asn_stats,
                "country_stats": country_stats,
                "eu_share": eu_share,
                "bad_country_share": bad_country_share,
                "avg_ping": avg_ping,
                "alive_ratio": alive_ratio,
                "last_seen": ts,
            }

            profiles[source] = profile

            out_path = self.base_dir / f"{source}.json"
            out_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return profiles

