"""
NodeFilter:
- dedup по (protocol, host, port, uuid/password)
- geo-фильтры из config.yaml
- performance-фильтры (alive_ratio/ping/asn) — частично заглушка
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .parser import VPNNode


@dataclass
class FilterStats:
    before: int = 0
    dropped_dup: int = 0
    dropped_filter: int = 0
    after: int = 0

    def to_dict(self) -> Dict:
        return {
            "before": self.before,
            "dropped_dup": self.dropped_dup,
            "dropped_filter": self.dropped_filter,
            "after": self.after,
        }


class NodeFilter:
    def __init__(self, config: Dict):
        self.config = config or {}
        self.geo_cfg = self.config.get("filters", {}).get("geo", {}) or {}
        self.perf_cfg = self.config.get("filters", {}).get("performance", {}) or {}
        self.asn_blacklist = set(
            self.config.get("filters", {}).get("asn_blacklist", []) or []
        )

    def apply(self, nodes: List[VPNNode]) -> Tuple[List[VPNNode], Dict]:
        stats = FilterStats()
        stats.before = len(nodes)

        # 1) dedup
        deduped = self._dedup(nodes)
        stats.dropped_dup = stats.before - len(deduped)

        # 2) geo/perf/asn фильтры
        filtered = self._apply_filters(deduped)
        stats.dropped_filter = len(deduped) - len(filtered)
        stats.after = len(filtered)

        return filtered, stats.to_dict()

    def _dedup(self, nodes: List[VPNNode]) -> List[VPNNode]:
        seen = set()
        result: List[VPNNode] = []

        for n in nodes:
            key = (
                n.protocol,
                n.host,
                n.port,
                n.uuid or n.password or "",
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(n)

        return result

    def _apply_filters(self, nodes: List[VPNNode]) -> List[VPNNode]:
        eu_only = self.geo_cfg.get("eu_only", False)
        exclude_countries = set(self.geo_cfg.get("exclude_countries", []) or [])
        whitelist_countries = self.geo_cfg.get("whitelist_countries")

        min_alive_ratio = self.perf_cfg.get("min_alive_ratio")
        min_ping = self.perf_cfg.get("min_ping_ms")
        max_ping = self.perf_cfg.get("max_ping_ms")

        eu_countries = {
            "DE","NL","FR","PL","SE","FI","IT","ES","CZ","AT","BE",
            "DK","IE","PT","RO","BG","SK","SI","GR","HU","HR","EE",
            "LV","LT","LU","CY","MT"
        }

        result: List[VPNNode] = []

        for n in nodes:
            extra = n.extra

            country = extra.get("country")
            asn = extra.get("asn")
            alive_ratio = extra.get("alive_ratio")
            ping = extra.get("ping")

            # Geo: исключить страны
            if country and country in exclude_countries:
                continue

            # Geo: whitelist
            if whitelist_countries and country and country not in whitelist_countries:
                continue

            # Geo: только EU
            if eu_only and country and country not in eu_countries:
                continue

            # ASN blacklist
            if asn and asn in self.asn_blacklist:
                continue

            # Performance: alive_ratio
            if min_alive_ratio is not None and alive_ratio is not None:
                if alive_ratio < min_alive_ratio:
                    continue

            # Performance: ping
            if min_ping is not None and ping is not None and ping < min_ping:
                continue
            if max_ping is not None and ping is not None and ping > max_ping:
                continue

            result.append(n)

        return result
