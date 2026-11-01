#!/usr/bin/env python3
"""
GeoIP pipeline под CI.

- читает ноды из out/by_type/*.txt (vless / vmess / ss),
- извлекает host (или IP) с учётом base64-форматов VMess и SS,
- резолвит host → IP (если это домен),
- по GeoLite2-Country.mmdb и GeoLite2-ASN.mmdb определяет country / ASN,
- пишет отчёт в sources_meta/geoip_report.md.

Отчёт пишется ВСЕГДА — даже если нет нод или нет MMDB.
Это гарантирует, что `git add sources_meta/geoip_report.md` в CI
не упадёт с `pathspec ... did not match any files`.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import socket
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import geoip2.database

OUT_DIR = Path("out")
META_DIR = Path("sources_meta")
DATA_DIR = Path("data")

BY_TYPE_FILES = [
    OUT_DIR / "by_type" / "vless.txt",
    OUT_DIR / "by_type" / "vmess.txt",
    OUT_DIR / "by_type" / "ss.txt",
]

MAX_NODES = 5000
REPORT_NAME = "geoip_report.md"


# ----------------------- Извлечение хоста из ноды -----------------------

def _split_host_port(hostport: str) -> Optional[str]:
    """'[2001:db8::1]:443' -> '2001:db8::1'; 'example.com:443' -> 'example.com'."""
    hostport = hostport.strip()
    if not hostport:
        return None
    if hostport.startswith("["):
        end = hostport.find("]")
        if end != -1:
            return hostport[1:end]
    if ":" in hostport:
        return hostport.rsplit(":", 1)[0]
    return hostport


def _b64decode_safe(s: str) -> str:
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s).decode("utf-8", "ignore")


def _extract_vmess(line: str) -> Optional[str]:
    try:
        obj = json.loads(_b64decode_safe(line[len("vmess://"):]))
        return obj.get("add") or None
    except Exception:
        return None


def _extract_ss(line: str) -> Optional[str]:
    try:
        body = line[len("ss://"):].split("#", 1)[0].split("?", 1)[0]
        if "@" in body:
            return _split_host_port(body.rsplit("@", 1)[1])
        decoded = _b64decode_safe(body)
        if "@" in decoded:
            return _split_host_port(decoded.rsplit("@", 1)[1])
    except Exception:
        return None
    return None


def _extract_uri_host(line: str) -> Optional[str]:
    try:
        return urlparse(line).hostname
    except Exception:
        return None


def extract_host_from_line(line: str) -> Optional[str]:
    line = line.strip()
    if not line:
        return None
    if line.startswith("vmess://"):
        return _extract_vmess(line)
    if line.startswith("ss://"):
        return _extract_ss(line)
    if "://" in line:
        return _extract_uri_host(line)
    return None


# ----------------------- Резолв хоста в IP -----------------------

@lru_cache(maxsize=8192)
def resolve_ip(host: str) -> Optional[str]:
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


# ----------------------- Сбор хостов -----------------------

def collect_hosts() -> List[str]:
    hosts: List[str] = []
    for path in BY_TYPE_FILES:
        if not path.exists():
            print(f"    skip missing: {path}", flush=True)
            continue
        print(f"    reading {path}", flush=True)
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            h = extract_host_from_line(line)
            if h:
                hosts.append(h)
                if len(hosts) >= MAX_NODES:
                    print(f"    hit MAX_NODES={MAX_NODES}, stopping", flush=True)
                    return hosts
    return hosts


# ----------------------- GeoIP readers -----------------------

def load_geoip_readers():
    country_path = DATA_DIR / "GeoLite2-Country.mmdb"
    asn_path = DATA_DIR / "GeoLite2-ASN.mmdb"

    geo_country = None
    geo_asn = None

    if country_path.exists():
        try:
            geo_country = geoip2.database.Reader(str(country_path))
            print(f"    loaded {country_path}", flush=True)
        except Exception as e:
            print(f"!!! failed to open {country_path}: {e}", flush=True)
    else:
        print(f"!!! {country_path} not found", flush=True)

    if asn_path.exists():
        try:
            geo_asn = geoip2.database.Reader(str(asn_path))
            print(f"    loaded {asn_path}", flush=True)
        except Exception as e:
            print(f"!!! failed to open {asn_path}: {e}", flush=True)
    else:
        print(f"!!! {asn_path} not found", flush=True)

    return geo_country, geo_asn


# ----------------------- Отчёт -----------------------

def write_report(
    total_hosts: int,
    resolved_ips: List[str],
    countries: Counter,
    asns: Counter,
    note: str = "",
) -> Path:
    report_path = META_DIR / REPORT_NAME
    lines: List[str] = ["# GeoIP report\n"]
    if note:
        lines.append(f"\n> ⚠️ {note}\n")
    lines.append(f"\n- Hosts collected: **{total_hosts}**\n")
    lines.append(f"- Resolved to IP: **{len(resolved_ips)}**\n")
    lines.append(f"- GeoIP lookups: **{sum(countries.values())}**\n")

    lines.append("\n## Top countries\n")
    if countries:
        for country, cnt in countries.most_common(20):
            lines.append(f"- {country}: {cnt}\n")
    else:
        lines.append("_no data_\n")

    lines.append("\n## Top ASNs\n")
    if asns:
        for (asn, org), cnt in asns.most_common(20):
            org = org or "(unknown)"
            lines.append(f"- AS{asn} {org}: {cnt}\n")
    else:
        lines.append("_no data_\n")

    lines.append("\n---\n_Generated by `geoip_pipeline.py`_\n")
    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"    → report saved to {report_path}", flush=True)
    return report_path


# ----------------------- Основной пайплайн -----------------------

def run_geoip() -> None:
    print(">>> geoip_pipeline.py started", flush=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    hosts = collect_hosts()
    print(f"    collected hosts: {len(hosts)}", flush=True)

    if not hosts:
        write_report(0, [], Counter(), Counter(), "no hosts parsed from out/by_type/*.txt")
        return

    geo_country, geo_asn = load_geoip_readers()
    if not geo_country and not geo_asn:
        write_report(len(hosts), [], Counter(), Counter(), "GeoLite2 databases not available")
        return

    resolved: List[str] = []
    country_counter: Counter[str] = Counter()
    asn_counter: Counter[Tuple[int, str]] = Counter()
    unresolved = 0

    for host in hosts:
        ip = resolve_ip(host)
        if not ip:
            unresolved += 1
            continue
        resolved.append(ip)

        if geo_country:
            try:
                iso = geo_country.country(ip).country.iso_code or "XX"
            except Exception:
                iso = "XX"
            country_counter[iso] += 1

        if geo_asn:
            try:
                a = geo_asn.asn(ip)
                asn_counter[(a.autonomous_system_number, a.autonomous_system_organization or "")] += 1
            except Exception:
                pass

    note = f"{unresolved} host(s) could not be resolved to IP" if unresolved else ""
    write_report(len(hosts), resolved, country_counter, asn_counter, note)
    print(">>> geoip_pipeline.py finished", flush=True)


if __name__ == "__main__":
    run_geoip()
