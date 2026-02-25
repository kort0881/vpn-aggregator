"""
Profiler:
- считает метрики по источникам (source_name в node.extra)
- считает метрики по провайдерам/первоисточникам (extra["provider_id"] или source_name)
- сохраняет JSON-профили:
    - по источникам в sources_meta/profiles/
    - по провайдерам в sources_meta/providers/

Базовая структура профиля:
{
  "id": str,
  "total_nodes": int,
  "unique_ips": int,
  "asn_stats": {asn: count},
  "country_stats": {country: count},
  "eu_share": float,
  "bad_country_share": float,
  "avg_ping": int|None,
  "median_ping": int|None,
  "alive_ratio": float|None,
  "last_seen": ISO8601,
  "score": float,
  "tags": [ ... ],
  "source_type": "first_party" | "aggregator" | "unknown"
}
"""

from __future__ import annotations

import json
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Tuple, Any, Callable

from .parser import VPNNode


class Profiler:
    def __init__(
        self,
        min_nodes: int = 5,
        base_dir_sources: str = "sources_meta/profiles",
        base_dir_providers: str = "sources_meta/providers",
        config: Dict | None = None,
    ):
        self.min_nodes = min_nodes
        self.base_dir_sources = Path(base_dir_sources)
        self.base_dir_providers = Path(base_dir_providers)

        self.base_dir_sources.mkdir(parents=True, exist_ok=True)
        self.base_dir_providers.mkdir(parents=True, exist_ok=True)

        self.config = config or {}
        geo_cfg = (self.config.get("filters") or {}).get("geo") or {}
        self.exclude_countries = set(geo_cfg.get("exclude_countries", []) or [])

        # тот же набор EU-стран, что и в фильтре
        self.eu_countries = {
            "DE", "NL", "FR", "PL", "SE", "FI", "IT", "ES", "CZ", "AT", "BE",
            "DK", "IE", "PT", "RO", "BG", "SK", "SI", "GR", "HU", "HR", "EE",
            "LV", "LT", "LU", "CY", "MT"
        }

        # "плохие" страны для bad_country_share
        self.bad_countries = {"RU", "BY", "IR", "CN"}

    # ──────────────────────────────────────────────────────
    # Публичный метод
    # ──────────────────────────────────────────────────────

    def build_profiles(self, nodes: List[VPNNode]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Строит:
          - profiles_by_source: профили по источникам (source_name)
          - profiles_by_provider: профили по провайдерам/первоисточникам (extra["provider_id"] или source_name)

        Возвращает:
        {
          "by_source": {source_id: profile_dict, ...},
          "by_provider": {provider_id: profile_dict, ...}
        }
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1) профили по source_name
        profiles_by_source = self._build_grouped_profiles(
            nodes=nodes,
            group_key_fn=lambda n: n.extra.get("source_name", "unknown"),
            out_dir=self.base_dir_sources,
            now_iso=now_iso,
        )

        # 2) профили по provider_id (первоисточники)
        def provider_key(n: VPNNode) -> str:
            extra = n.extra or {}
            return extra.get("provider_id") or extra.get("source_name", "unknown")

        profiles_by_provider = self._build_grouped_profiles(
            nodes=nodes,
            group_key_fn=provider_key,
            out_dir=self.base_dir_providers,
            now_iso=now_iso,
        )

        return {
            "by_source": profiles_by_source,
            "by_provider": profiles_by_provider,
        }

    # ──────────────────────────────────────────────────────
    # Внутреннее: построение групповых профилей
    # ──────────────────────────────────────────────────────

    def _build_grouped_profiles(
        self,
        nodes: List[VPNNode],
        group_key_fn: Callable[[VPNNode], str],
        out_dir: Path,
        now_iso: str,
    ) -> Dict[str, Dict[str, Any]]:
        by_group: Dict[str, List[VPNNode]] = defaultdict(list)

        for n in nodes:
            key = group_key_fn(n) or "unknown"
            by_group[key].append(n)

        profiles: Dict[str, Dict[str, Any]] = {}

        for group_id, lst in by_group.items():
            if len(lst) < self.min_nodes:
                # можно пропускать редкие источники, если хочется
                pass

            profile = self._build_single_profile(group_id, lst, now_iso)
            profiles[group_id] = profile

            out_path = out_dir / f"{group_id}.json"
            out_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return profiles

    # ──────────────────────────────────────────────────────
    # Один профиль (общая логика)
    # ──────────────────────────────────────────────────────

    def _build_single_profile(
        self,
        entity_id: str,
        nodes: List[VPNNode],
        now_iso: str,
    ) -> Dict[str, Any]:
        # базовые коллекции
        ips: List[str] = []
        countries: List[str] = []
        asns: List[int] = []
        pings: List[float] = []
        alive_flags: List[bool] = []
        last_seen_ts: float | None = None
        last_seen_iso: str | None = None

        for n in nodes:
            extra = n.extra or {}
            ip = extra.get("ip")
            if ip:
                ips.append(ip)

            country = extra.get("country")
            if country:
                countries.append(country)

            asn = extra.get("asn")
            if asn is not None:
                asns.append(asn)

            ping = extra.get("ping")
            if isinstance(ping, (int, float)):
                pings.append(float(ping))

            alive = extra.get("alive")
            if isinstance(alive, bool):
                alive_flags.append(alive)

            ts = extra.get("last_seen_ts")
            if isinstance(ts, (int, float)):
                if last_seen_ts is None or ts > last_seen_ts:
                    last_seen_ts = ts
                    last_seen_iso = extra.get("last_seen_iso") or extra.get("last_seen") or now_iso

        total_nodes = len(nodes)
        unique_ips = len(set(ips)) if ips else 0

        # ASN и страны
        asn_stats = dict(Counter(asns))
        country_stats = dict(Counter(countries))

        total_with_country = sum(country_stats.values()) or 1

        eu_count = sum(country_stats.get(c, 0) for c in self.eu_countries)
        eu_share = eu_count / total_with_country

        bad_count = sum(country_stats.get(c, 0) for c in self.bad_countries)
        bad_country_share = bad_count / total_with_country

        avg_ping = int(mean(pings)) if pings else None
        median_ping = int(median(pings)) if pings else None

        alive_ratio = (
            (sum(1 for a in alive_flags if a) / len(alive_flags))
            if alive_flags else None
        )

        score, tags = self._compute_score_and_tags(
            eu_share=eu_share,
            bad_share=bad_country_share,
            alive_ratio=alive_ratio,
            total_nodes=total_nodes,
        )

        source_type = self._classify_source_type(
            total_nodes=total_nodes,
            unique_ips=unique_ips,
            asn_stats=asn_stats,
        )

        # добавляем тип источника в теги для удобного поиска
        if source_type == "first_party":
            tags.append("first_party_like")
        elif source_type == "aggregator":
            tags.append("aggregator_like")

        profile = {
            "id": entity_id,
            "total_nodes": total_nodes,
            "unique_ips": unique_ips,
            "asn_stats": asn_stats,
            "country_stats": country_stats,
            "eu_share": eu_share,
            "bad_country_share": bad_country_share,
            "avg_ping": avg_ping,
            "median_ping": median_ping,
            "alive_ratio": alive_ratio,
            "last_seen": last_seen_iso or now_iso,
            "score": score,
            "tags": tags,
            "source_type": source_type,
        }
        return profile

    # ──────────────────────────────────────────────────────
    # Классификация: первоисточник vs агрегатор
    # ──────────────────────────────────────────────────────

    def _classify_source_type(
        self,
        total_nodes: int,
        unique_ips: int,
        asn_stats: Dict[int, int],
    ) -> str:
        """
        Возвращает:
          - 'first_party'  — похоже на свои сервера/панель
          - 'aggregator'   — похоже на сборник чужих конфигов
          - 'unknown'      — неясно
        Эвристики:
          - first_party: высокий перекос в один ASN, относительно низкое разнообразие IP
          - aggregator: много разных ASN и почти каждый узел с уникальным IP
        """
        if total_nodes < 10:
            return "unknown"

        total_nodes_f = float(total_nodes)
        ip_diversity = unique_ips / total_nodes_f if total_nodes > 0 else 0.0

        if asn_stats:
            top_asn_count = max(asn_stats.values())
            asn_concentration = top_asn_count / total_nodes_f
            asn_diversity = len(asn_stats)
        else:
            asn_concentration = 0.0
            asn_diversity = 0

        # Кандидат в первоисточники: один-два ASN тянут 70%+ узлов,
        # IP диверсификация не экстремально высокая.
        if asn_concentration >= 0.7 and ip_diversity <= 0.4:
            return "first_party"

        # Явный агрегатор: очень много разных ASN и почти каждый IP уникален.
        if asn_diversity >= 15 and ip_diversity >= 0.75:
            return "aggregator"

        return "unknown"

    # ──────────────────────────────────────────────────────
    # Score + теги
    # ──────────────────────────────────────────────────────

    def _compute_score_and_tags(
        self,
        eu_share: float,
        bad_share: float,
        alive_ratio: float | None,
        total_nodes: int,
    ) -> Tuple[float, List[str]]:
        import math

        alive_ratio_val = alive_ratio if alive_ratio is not None else 0.0

        base = 0.0
        base += 2.0 * eu_share
        base -= 3.0 * bad_share
        base += 1.5 * alive_ratio_val
        base += 0.2 * math.log1p(total_nodes)

        score = round(base, 3)

        tags: List[str] = []
        # кандидаты в whitelist
        if eu_share >= 0.7 and bad_share <= 0.1 and alive_ratio_val >= 0.5 and total_nodes >= self.min_nodes:
            tags.append("whitelist_candidate")

        # кандидаты в blacklist
        if bad_share >= 0.5 or alive_ratio_val <= 0.1:
            tags.append("blacklist_candidate")

        return score, tags
