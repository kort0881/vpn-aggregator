#!/usr/bin/env python3
"""
GeoIP pipeline под CI:

- читает итоговые ноды из out/by_type/*.txt (vless/vmess/ss),
- вытаскивает IP (если есть) или host,
- по GeoLite2-Country.mmdb и GeoLite2-ASN.mmdb определяет country / ASN,
- пишет агрегированную статистику по странам и ASN в sources_meta/geoip_report.md.

Работает только по части нод (лимит), чтобы не грузить CI.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import geoip2.database

OUT_DIR = Path("out")
META_DIR = Path("sources_meta")
DATA_DIR = Path("data")

BY_TYPE_FILES = [
    OUT_DIR / "by_type" / "vless.txt",
    OUT_DIR / "by_type" / "vmess.txt",
    OUT_DIR / "by_type" / "ss.txt",
]

MAX_NODES = 5000  # лимит нод, по которым делаем GeoIP в CI


def load_geoip_readers() -> Tuple[Optional[geoip2.database.Reader], Optional[geoip2.database.Reader]]:
    country_path = DATA_DIR / "GeoLite2-Country.mmdb"
    asn_path = DATA_DIR / "GeoLite2-ASN.mmdb"

    geo_country = None
    geo_asn = None

    if country_path.exists():
        geo_country = geoip2.database.Reader(str(country_path))
    else:
        print(f"!!! GeoLite2-Country.mmdb not found at {country_path}")

    if asn_path.exists():
        geo_asn = geoip2.database.Reader(str(asn_path))
    else:
        print(f"!!! GeoLite2-ASN.mmdb not found at {asn_path}")

    return geo_country, geo_asn


def extract_ip_from_line(line: str) -> Optional[str]:
    """
    Очень грубый разбор:
    ищем 'ip=' или 'host=' в remark/URI.
    Настрой под свой формат, если нужно точнее.
    """
    line = line.strip()
    if not line or "://" not in line:
        return None

    # пример: vless://user@host:port?param=...
    try:
        main_part = line.split("://", 1)[1]
        host_port = main_part.split("?", 1)[0]
        host = host_port.split("@")[-1].split(":")[0]
        if host and any(c.isdigit() for c in host):
            # ip-v4/v6 или домен, GeoIP сам умеет принимать host
            return host
    except Exception:
        return None

    return None


def collect_ips() -> List[str]:
    ips: List[str] = []
    for path in BY_TYPE_FILES:
        if not path.exists():
            continue
        print(f"    reading {path}")
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            ip = extract_ip_from_line(line)
            if ip:
                ips.append(ip)
                if len(ips) >= MAX_NODES:
                    return ips
    return ips


def run_geoip() -> None:
    print(">>> geoip_pipeline.py started", flush=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    ips = collect_ips()
    print(f"    collected IP/hosts for lookup: {len(ips)}", flush=True)

    if not ips:
        print("    no IPs found, nothing to do", flush=True)
        return

    geo_country, geo_asn = load_geoip_readers()
    if not geo_country and not geo_asn:
        print("    no GeoIP databases available, abort", flush=True)
        return

    country_counter: Counter[str] = Counter()
    asn_counter: Counter[Tuple[int, str]] = Counter()

    for ip in ips:
        country = "XX"
        if geo_country:
            try:
                c = geo_country.country(ip)
                country = c.country.iso_code or "XX"
            except Exception:
                country = "XX"

        country_counter[country] += 1

        if geo_asn:
            try:
                a = geo_asn.asn(ip)
                asn = a.autonomous_system_number
                org = a.autonomous_system_organization or ""
                asn_counter[(asn, org)] += 1
            except Exception:
                pass

    report_path = META_DIR / "geoip_report.md"
    lines = []
    lines.append("# GeoIP report\n")
    lines.append(f"Total IPs looked up: {len(ips)}\n")

    lines.append("\n## Top countries\n")
    for country, cnt in country_counter.most_common(20):
        lines.append(f"- {country}: {cnt}\n")

    lines.append("\n## Top ASNs\n")
    for (asn, org), cnt in asn_counter.most_common(20):
        lines.append(f"- AS{asn} {org}: {cnt}\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"    → report saved to {report_path}", flush=True)
    print(">>> geoip_pipeline.py finished", flush=True)


if __name__ == "__main__":
    run_geoip()
