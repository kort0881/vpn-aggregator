#!/usr/bin/env python3
"""
Упрощённый VPN pipeline под CI:

  1. load_config  — читаем config.yaml
  2. ingest       — качаем источники → sources_raw/*.txt
  3. parse        — парсим в VPNNode[]
  4. enrich-lite  — только DNS resolve (без GeoIP и ping), с лимитом в CI
  5. status       — пишем краткий статус в out/status.txt
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import List

import requests
import yaml

from scripts.parser import ConfigParser, VPNNode
from scripts.enricher import Enricher, EnricherConfig


SOURCES_RAW_DIR = Path("sources_raw")
OUT_DIR = Path("out")


def load_config(path: str = "config.yaml") -> dict:
    print(">>> [config] loading config.yaml", flush=True)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("!!! config.yaml not found, using empty config", flush=True)
        return {}
    except yaml.YAMLError as exc:
        print(f"!!! error parsing config.yaml: {exc}", flush=True)
        return {}

    print(f">>> [config] sections: {list(cfg.keys())}", flush=True)
    return cfg


def ingest_sources(cfg: dict) -> None:
    print("\n[1/4] Ingesting sources...", flush=True)
    SOURCES_RAW_DIR.mkdir(parents=True, exist_ok=True)

    sources_cfg = cfg.get("sources", {}) or {}
    if not sources_cfg:
        print("    no sources in config", flush=True)
        return

    total_ok = total_fail = 0

    for group_name, group_list in sources_cfg.items():
        if not isinstance(group_list, list):
            continue
        print(f"    group: {group_name}", flush=True)

        for src in group_list:
            if not isinstance(src, dict) or not src.get("enabled", True):
                continue
            name = src.get("name") or "noname"
            url = (src.get("url") or "").strip()
            if not url:
                continue

            try:
                resp = requests.get(
                    url,
                    timeout=10,  # агрессивный таймаут для CI
                    headers={"User-Agent": "Mozilla/5.0"},
                    allow_redirects=True,
                )
                resp.raise_for_status()
                (SOURCES_RAW_DIR / f"{name}.txt").write_text(
                    resp.text, encoding="utf-8"
                )
                total_ok += 1
            except Exception as exc:
                print(f"      ✗ {name}: {exc}", flush=True)
                total_fail += 1

    print(f"    fetched: {total_ok}, failed: {total_fail}", flush=True)


def parse_sources(parser: ConfigParser) -> List[VPNNode]:
    print("\n[2/4] Parsing & normalising...", flush=True)
    if not SOURCES_RAW_DIR.exists():
        print("    sources_raw/ does not exist, nothing to parse", flush=True)
        return []

    all_nodes: List[VPNNode] = []
    total_raw = 0

    for path in sorted(SOURCES_RAW_DIR.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print(f"    ! Cannot read {path.name}: {exc}", flush=True)
            continue

        source_name = path.stem
        nodes = parser.parse_text(text, source=source_name)
        total_raw += len(text.splitlines())
        all_nodes.extend(nodes)
        print(f"      {path.name}: {len(nodes)} nodes", flush=True)

    print(
        f"    → raw lines: {total_raw}  nodes parsed: {len(all_nodes)}",
        flush=True,
    )
    return all_nodes


def enrich_nodes_dns_only(nodes: List[VPNNode]) -> None:
    print("\n[3/4] Enriching nodes (DNS only)...", flush=True)
    if not nodes:
        print("    no nodes to enrich", flush=True)
        return

    cfg = EnricherConfig()
    # DNS включен, GeoIP и ping — нет
    cfg.enable_dns = True
    cfg.enable_geoip = False
    cfg.enable_alive = False

    # В CI режем объём и таймауты
    if os.environ.get("CI"):
        cfg.max_nodes_per_run = 1000  # обогащаем только верхние 1000 нод
        cfg.dns_timeout = 2.0

    print(
        f"    enricher config: dns={cfg.enable_dns} geoip={cfg.enable_geoip} "
        f"alive={cfg.enable_alive} max_nodes_per_run={cfg.max_nodes_per_run}",
        flush=True,
    )

    enricher = Enricher(config=cfg, debug=False)
    enricher.enrich_all(nodes)

    with_ip = sum(1 for n in nodes if n.extra.get("ip"))
    print(
        f"    → nodes total: {len(nodes)}  with ip: {with_ip}",
        flush=True,
    )


def write_status(nodes: List[VPNNode]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status_file = OUT_DIR / "status.txt"
    now = datetime.datetime.utcnow().isoformat()
    with_ip = sum(1 for n in nodes if n.extra.get("ip"))
    status_file.write_text(
        f"Last run: {now}Z\n"
        f"Parsed nodes: {len(nodes)}\n"
        f"With IP (after DNS): {with_ip}\n",
        encoding="utf-8",
    )
    print(f"\n[4/4] wrote {status_file}", flush=True)


def main() -> None:
    print(">>> pipeline.py started (config + ingest + parse + enrich-dns)", flush=True)

    cfg = load_config()
    ingest_sources(cfg)

    parser = ConfigParser()
    nodes = parse_sources(parser)

    enrich_nodes_dns_only(nodes)

    write_status(nodes)

    print(">>> pipeline.py finished", flush=True)


if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()


