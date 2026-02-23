"""
Enricher:
- DNS resolve (host -> ip)
- GeoIP (country, asn) через локальные/автоскачиваемые MaxMind-базы
- Alive/ping через TCP connect
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import geoip2.database
import requests

from .parser import VPNNode


@dataclass
class EnricherConfig:
    dns_timeout: float = 2.0

    enable_dns: bool = True
    enable_geoip: bool = True
    enable_alive: bool = True

    # каталоги и URL для автозагрузки баз GeoIP
    db_dir: str = "data"
    country_db_filename: str = "GeoLite2-Country.mmdb"
    asn_db_filename: str = "GeoLite2-ASN.mmdb"

    # сюда впиши свои реальные URL к .mmdb (из своего хранилища / CDN)
    country_db_url: str = "https://example.com/GeoLite2-Country.mmdb"
    asn_db_url: str = "https://example.com/GeoLite2-ASN.mmdb"

    # лимит на количество нод для энричмента за один прогон (чтобы не умирать на десятках тысяч)
    max_nodes_per_run: int = 5000

    # таймаут TCP-ping
    ping_timeout: float = 1.5


class Enricher:
    def __init__(self, config: Optional[EnricherConfig] = None, debug: bool = False):
        self.config = config or EnricherConfig()
        self.debug = debug

        self.db_dir = Path(self.config.db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self.country_db_path = self.db_dir / self.config.country_db_filename
        self.asn_db_path = self.db_dir / self.config.asn_db_filename

        self._geo_country = None
        self._geo_asn = None

        if self.config.enable_geoip:
            self._ensure_db(self.country_db_path, self.config.country_db_url)
            self._ensure_db(self.asn_db_path, self.config.asn_db_url)

            # Открываем базы только если они реально существуют
            if self.country_db_path.exists():
                self._geo_country = geoip2.database.Reader(str(self.country_db_path))
            if self.asn_db_path.exists():
                self._geo_asn = geoip2.database.Reader(str(self.asn_db_path))

    def _ensure_db(self, path: Path, url: str) -> None:
        """Скачать .mmdb, если его ещё нет."""
        if path.exists():
            return
        if not url:
            return
        if self.debug:
            print(f"      [GeoIP] downloading {url} -> {path}")
        try:
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            with path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as exc:
            if self.debug:
                print(f"      [GeoIP] failed to download {url}: {exc}")

    def enrich_all(self, nodes: List[VPNNode]) -> None:
        """Массовое обогащение нод (DNS + GeoIP + ping)."""
        max_n = self.config.max_nodes_per_run or len(nodes)
        for i, node in enumerate(nodes):
            if i >= max_n:
                break
            self._enrich_node(node)

    def _enrich_node(self, node: VPNNode) -> None:
        extra = node.extra

        # DNS resolve
        if self.config.enable_dns and "ip" not in extra:
            ip = self._resolve_ip(node.host)
            if ip:
                extra["ip"] = ip
                if self.debug:
                    print(f"      [DNS] {node.host} -> {ip}")

        ip = extra.get("ip")
        if not ip:
            return

        # GeoIP: country + ASN
        if self.config.enable_geoip:
            # country
            if self._geo_country:
                try:
                    c = self._geo_country.country(ip)
                    extra["country"] = c.country.iso_code
                except Exception:
                    extra.setdefault("country", None)
            # ASN
            if self._geo_asn:
                try:
                    a = self._geo_asn.asn(ip)
                    extra["asn"] = a.autonomous_system_number
                    extra["asn_name"] = a.autonomous_system_organization
                except Exception:
                    extra.setdefault("asn", None)

        # Alive / ping через TCP connect
        if self.config.enable_alive:
            ping_ms = self._tcp_ping(ip or node.host, node.port, timeout=self.config.ping_timeout)
            if ping_ms is None:
                extra["alive"] = False
                extra["ping"] = None
            else:
                extra["alive"] = True
                extra["ping"] = int(ping_ms)

    def _resolve_ip(self, host: str) -> Optional[str]:
        try:
            return socket.gethostbyname(host)
        except Exception:
            return None

    def _tcp_ping(self, host: str, port: int, timeout: float = 1.5) -> Optional[float]:
        """Простой TCP 'ping' — время установления TCP-соединения в мс."""
        try:
            start = time.monotonic()
            with socket.create_connection((host, port), timeout=timeout):
                end = time.monotonic()
            return (end - start) * 1000.0
        except Exception:
            return None

