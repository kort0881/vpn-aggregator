#!/usr/bin/env python3
"""
Упрощённый VPN pipeline:

  1. load_config  — читаем config.yaml
  2. ingest       — качаем источники → sources_raw/*.txt
  3. parse        — парсим в VPNNode[] (без обогащения/фильтров)
  4. status       — пишем краткий статус в out/status.txt
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import List

import requests
import yaml

from scripts.parser import ConfigParser, VPNNode


SOURCES_RAW_DIR = Path("sources_raw")
OUT_DIR = Path("out")


def load_config(path: str = "config.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"!!! config.yaml not found, using empty config")
        return {}
    except yaml.YAMLError as exc:
        print(f"!!! error parsing config.yaml: {exc}")
        return {}

    print(f">>> config loaded, sections: {list(cfg.keys())}")
    return cfg


def ingest_sources(cfg: dict) -> None:
    print("\n[1/3] Ingesting sources...")
    SOURCES_RAW_DIR.mkdir(parents=True, exist_ok=True)

    sources_cfg = cfg.get("sources", {}) or {}
    if not sources_cfg:
        print("    no sources in config")
        return

    total_ok = total_fail = 0

    for group_name, group_list in sources_cfg.items():
        if not isinstance(group_list, list):
            continue
        print(f"    group: {group_name}")

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
                print(f"      ✗ {name}: {exc}")
                total_fail += 1

    print(f"    fetched: {total_ok}, failed: {total_fail}")


def parse_sources(parser: ConfigParser) -> List[VPNNode]:
    print("\n[2/3] Parsing & normalising...")
    if not SOURCES_RAW_DIR.exists():
        print("    sources_raw/ does not exist, nothing to parse")
        return []

    all_nodes: List[VPNNode] = []
    total_raw = 0

    for path in sorted(SOURCES_RAW_DIR.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print(f"    ! Cannot read {path.name}: {exc}")
            continue

        source_name = path.stem
        nodes = parser.parse_text(text, source=source_name)
        total_raw += len(text.splitlines())
        all_nodes.extend(nodes)
        print(f"      {path.name}: {len(nodes)} nodes")

    print(f"    → raw lines: {total_raw}  nodes parsed: {len(all_nodes)}")
    return all_nodes


def write_status(nodes: List[VPNNode]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status_file = OUT_DIR / "status.txt"
    now = datetime.datetime.utcnow().isoformat()
    status_file.write_text(
        f"Last run: {now}Z\nParsed nodes: {len(nodes)}\n",
        encoding="utf-8",
    )
    print(f"\n[3/3] wrote {status_file}")


def main() -> None:
    print(">>> pipeline.py started (config + ingest + parse)")

    cfg = load_config()
    ingest_sources(cfg)

    parser = ConfigParser()
    nodes = parse_sources(parser)

    write_status(nodes)

    print(">>> pipeline.py finished")


if __name__ == "__main__":
    main()


