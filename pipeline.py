#!/usr/bin/env python3
"""
VPN Aggregator Pipeline

Main orchestrator for the VPN config aggregation, filtering, and repacking pipeline.
"""

import sys
import yaml
import requests
from pathlib import Path
from scripts.parser import ConfigParser


class VPNAggregatorPipeline:
    """Main pipeline orchestrator"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.parser = ConfigParser()

        # краткие шорткаты к настройкам
        self.output_cfg = self.config.get("output", {}) or {}
        self.filters_cfg = self.config.get("filters", {}) or {}
        self.base_out = Path(self.output_cfg.get("base_path", "./out"))

    def load_config(self) -> dict:
        """Load configuration from YAML"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Error: Config file '{self.config_path}' not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing config: {e}")
            sys.exit(1)

    def ensure_directories(self):
        """Create necessary directories"""
        dirs = [
            Path("sources_raw"),
            Path("sources_clean"),
            Path("sources_meta/profiles"),
            self.base_out / "by_type",
            self.base_out / "by_country",
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
        print("[+] Directories structure created")

    def fetch_sources(self):
        """Step 1: Fetch raw configs from sources (config-driven)"""
        print("\n[1/4] Fetching sources...")
        sources_cfg = self.config.get("sources", {}) or {}
        raw_dir = Path("sources_raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        if not sources_cfg:
            print("    ! No sources defined in config.yaml under 'sources'")
            return

        total_ok = 0
        total_failed = 0

        for group_name, group_sources in sources_cfg.items():
            print(f"    Group: {group_name}")
            if not isinstance(group_sources, list):
                print(f"      ! Skipped: group '{group_name}' is not a list")
                continue

            for src in group_sources:
                if not isinstance(src, dict):
                    continue

                if not src.get("enabled", True):
                    continue

                name = src.get("name") or "noname"
                url = src.get("url")
                if not url:
                    print(f"      - {name}: skipped (no url)")
                    continue

                print(f"      - {name}: {url}")
                try:
                    resp = requests.get(url, timeout=25)
                    resp.raise_for_status()
                    (raw_dir / f"{name}.txt").write_text(resp.text, encoding="utf-8")
                    total_ok += 1
                except Exception as e:
                    print(f"        ! failed: {e}")
                    total_failed += 1

        print(f"    → fetched: {total_ok}, failed: {total_failed}")

    def filter_and_classify(self):
        """Step 2: Filter by geo and classify (stub for now)"""
        print("\n[2/4] Filtering and classifying...")

        geo_cfg = self.filters_cfg.get("geo", {}) or {}
        eu_only = geo_cfg.get("eu_only", False)
        exclude_countries = geo_cfg.get("exclude_countries", []) or []
        whitelist_countries = geo_cfg.get("whitelist_countries")

        print(f"    - EU only: {eu_only}")
        print(f"    - Exclude countries: {', '.join(exclude_countries) if exclude_countries else 'none'}")
        if whitelist_countries:
            print(f"    - Whitelist countries: {', '.join(whitelist_countries)}")
        else:
            print("    - Whitelist countries: not set")

        # TODO: здесь позже:
        #  - пройти по sources_clean / нормализованным конфигам
        #  - применить geo-фильтры (country/region)
        #  - разнести по временным структурам (по типу/стране)

    def collect_provider_profiles(self):
        """Step 3: Build provider profiles (stub for now)"""
        print("\n[3/4] Building provider profiles...")
        print("    - Analyzing ASN distribution (TODO)")
        print("    - Calculating alive ratios (TODO)")
        print("    - Updating whitelist/blacklist (TODO)")

    def repack_configs(self):
        """Step 4: Repack and rebrand configs (minimal stub)"""
        print("\n[4/4] Repacking configs...")
        brand = self.config.get("app", {}).get("brand_name", "@myChannel")
        template = self.output_cfg.get("format_template", "{country} {ping}ms AS{asn} {protocol}")

        print(f"    - Brand: {brand}")
        print(f"    - Template: {template}")

        # Заглушка: пока просто создаём пустые файлы-местозаполнители,
        # чтобы GitHub Actions видел артефакты в out/
        by_type_dir = self.base_out / "by_type"
        by_country_dir = self.base_out / "by_country"
        by_type_dir.mkdir(parents=True, exist_ok=True)
        by_country_dir.mkdir(parents=True, exist_ok=True)

        # Простейшие плейсхолдеры (можно удалить, когда внедришь реальный репак)
        (by_type_dir / "vless.txt").write_text("", encoding="utf-8")
        (by_type_dir / "vmess.txt").write_text("", encoding="utf-8")
        (by_type_dir / "shadowsocks.txt").write_text("", encoding="utf-8")

        # TODO: позже:
        #  - читать нормализованные конфиги
        #  - для каждого считать строку вида template.format(...)
        #  - учитывать split_by_country / split_by_type
        #  - использовать self.parser для переупаковки URI с новым remark/tag

        print(f"    - Placeholder files created in: {self.base_out}")

    def run(self):
        """Run the complete pipeline"""
        print("=" * 60)
        print("VPN Aggregator Pipeline")
        print("=" * 60)

        self.ensure_directories()
        self.fetch_sources()
        self.filter_and_classify()
        self.collect_provider_profiles()
        self.repack_configs()

        print("\n" + "=" * 60)
        print("Pipeline completed successfully!")
        print("=" * 60)


def main():
    """Entry point"""
    pipeline = VPNAggregatorPipeline()
    pipeline.run()


if __name__ == "__main__":
    main()

