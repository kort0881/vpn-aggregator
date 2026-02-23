#!/usr/bin/env python3
"""
pipeline.py
Главный оркестратор VPN Aggregator Pipeline.

Шаги:
  1. Ingest      — скачать источники из config.yaml → sources_raw/
  2. Parse       — разобрать все *.txt в VPNNode[]
  3. Enrich      — резолв IP, GeoIP, alive/ping
  4. Filter      — geo / performance / asn_blacklist + dedup
  5. Profile     — метрики по источникам и провайдерам → sources_meta/profiles/, sources_meta/providers/
  6. Repack      — rebuild URI + remark + base64 → out/
  7. Report      — markdown summary → sources_meta/pipeline_report.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List

import requests
import yaml

from scripts.enricher import Enricher
from scripts.filters import NodeFilter
from scripts.parser import ConfigParser, VPNNode
from scripts.profiler import Profiler
from scripts.repacker import Repacker
from scripts.reporter import Reporter


class VPNAggregatorPipeline:

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

        app = self.config.get("app", {}) or {}
        self.debug = app.get("debug", False)
        self.brand = app.get("brand_name", "@vpn")

        quality = self.config.get("quality_metrics", {}) or {}
        self.min_nodes_per_source = quality.get("min_nodes_per_source", 5)

        out_cfg = self.config.get("output", {}) or {}
        self.base_out = Path(out_cfg.get("base_path", "./out"))

        self.parser = ConfigParser()
        self.enricher = Enricher(debug=self.debug)
        self.filterer = NodeFilter(self.config)
        self.profiler = Profiler(
            min_nodes=self.min_nodes_per_source,
            config=self.config,
        )
        self.repacker = Repacker(self.config)
        self.reporter = Reporter()

        self.nodes: List[VPNNode] = []

    def run(self) -> None:
        t_start = time.monotonic()
        self._banner("VPN Aggregator Pipeline")

        self._ensure_dirs()
        self._step1_ingest()
        raw_count = self._step2_parse()
        self._step3_enrich()
        filter_stats = self._step4_filter()
        profiles = self._step5_profile()
        self._step6_repack()
        self._step7_report(raw_count, filter_stats, profiles)

        elapsed = time.monotonic() - t_start
        self._banner(f"Done in {elapsed:.1f}s  |  {len(self.nodes)} nodes in out/")

    # ── шаг 1: Ingest ────────────────────────────────────────

    def _step1_ingest(self) -> None:
        print("\n[1/7] Ingesting sources...")
        raw_dir = Path("sources_raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        sources_cfg = self.config.get("sources", {}) or {}
        if not sources_cfg:
            print("    ! No sources defined in config.yaml")
            return

        total_ok = total_fail = 0

        for group_name, group_list in sources_cfg.items():
            if not isinstance(group_list, list):
                continue
            print(f"    Group: {group_name}")

            for src in group_list:
                if not isinstance(src, dict) or not src.get("enabled", True):
                    continue
                name = src.get("name") or "noname"
                url = src.get("url", "").strip()
                if not url:
                    continue

                try:
                    resp = requests.get(
                        url,
                        timeout=25,
                        headers={"User-Agent": "Mozilla/5.0"},
                        allow_redirects=True,
                    )
                    resp.raise_for_status()
                    ct = resp.headers.get("Content-Type", "")
                    if "text/html" in ct and "<html" in resp.text[:200].lower():
                        raise ValueError("Got HTML instead of config")

                    (raw_dir / f"{name}.txt").write_text(resp.text, encoding="utf-8")
                    total_ok += 1
                    if self.debug:
                        print(f"      ✓ {name}")
                except Exception as exc:
                    print(f"      ✗ {name}: {exc}")
                    total_fail += 1

        print(f"    → fetched: {total_ok}  failed: {total_fail}")

    # ── шаг 2: Parse ─────────────────────────────────────────

    def _step2_parse(self) -> int:
        """Вернуть суммарное количество разобранных строк (до фильтрации)."""
        print("\n[2/7] Parsing & normalising...")
        raw_dir = Path("sources_raw")
        if not raw_dir.exists():
            print("    ! sources_raw/ missing")
            return 0

        all_nodes: List[VPNNode] = []
        total_raw = 0

        for path in sorted(raw_dir.glob("*.txt")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                print(f"    ! Cannot read {path.name}: {exc}")
                continue

            source_name = path.stem
            nodes = self.parser.parse_text(text, source=source_name)
            total_raw += len(text.splitlines())
            all_nodes.extend(nodes)

            if self.debug:
                print(f"      {path.name}: {len(nodes)} nodes")

        self.nodes = all_nodes
        print(f"    → raw lines: {total_raw}  nodes parsed: {len(self.nodes)}")
        return len(self.nodes)

    # ── шаг 3: Enrich ────────────────────────────────────────

    def _step3_enrich(self) -> None:
        print("\n[3/7] Enriching nodes (DNS + GeoIP + alive)...")
        if not self.nodes:
            print("    ! No nodes to enrich")
            return
        self.enricher.enrich_all(self.nodes)

    # ── шаг 4: Filter ────────────────────────────────────────

    def _step4_filter(self) -> dict:
        print("\n[4/7] Filtering...")
        geo = self.config.get("filters", {}).get("geo", {}) or {}
        print(
            f"    eu_only={geo.get('eu_only')}  "
            f"exclude={geo.get('exclude_countries')}  "
            f"whitelist={geo.get('whitelist_countries')}"
        )

        self.nodes, stats = self.filterer.apply(self.nodes)
        print(
            f"    → before: {stats['before']}  "
            f"dup dropped: {stats['dropped_dup']}  "
            f"filtered: {stats['dropped_filter']}  "
            f"after: {stats['after']}"
        )
        return stats

    # ── шаг 5: Profile ───────────────────────────────────────

    def _step5_profile(self) -> dict:
        print("\n[5/7] Building profiles (sources + providers)...")
        profiles = self.profiler.build_profiles(self.nodes)

        by_source = profiles.get("by_source", {})
        by_provider = profiles.get("by_provider", {})

        print(
            f"    → source profiles: {len(by_source)} saved to sources_meta/profiles/"
        )
        print(
            f"    → provider profiles: {len(by_provider)} saved to sources_meta/providers/"
        )

        return profiles

    # ── шаг 6: Repack ────────────────────────────────────────

    def _step6_repack(self) -> None:
        print("\n[6/7] Repacking & branding...")
        self.repacker.repack(self.nodes)

    # ── шаг 7: Report ────────────────────────────────────────

    def _step7_report(self, raw_count: int, filter_stats: dict, profiles: dict) -> None:
        print("\n[7/7] Generating report...")
        report = self.reporter.generate(
            nodes_raw=raw_count,
            nodes_final=self.nodes,
            filter_stats=filter_stats,
            source_profiles=profiles,
        )
        print("    → report saved to sources_meta/pipeline_report.md")

        import os
        ghs = os.environ.get("GITHUB_STEP_SUMMARY")
        if ghs:
            try:
                Path(ghs).open("a", encoding="utf-8").write(report)
            except Exception:
                pass

    # ── утилиты ──────────────────────────────────────────────

    def _load_config(self) -> dict:
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Error: config file '{self.config_path}' not found")
            sys.exit(1)
        except yaml.YAMLError as exc:
            print(f"Error parsing config: {exc}")
            sys.exit(1)

    def _ensure_dirs(self) -> None:
        dirs = [
            Path("sources_raw"),
            Path("sources_clean"),
            Path("sources_meta/profiles"),
            Path("sources_meta/providers"),
            self.base_out / "by_type",
            self.base_out / "by_country",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _banner(text: str) -> None:
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60)


def main() -> None:
        import argparse

        ap = argparse.ArgumentParser(description="VPN Aggregator Pipeline")
        ap.add_argument("--config", default="config.yaml", help="Path to config.yaml")
        args = ap.parse_args()

        pipeline = VPNAggregatorPipeline(config_path=args.config)
        pipeline.run()


if __name__ == "__main__":
    main()
