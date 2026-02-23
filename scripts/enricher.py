from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import geoip2.database

from .parser import VPNNode


@dataclass
class EnricherConfig:
    dns_timeout: float = 1.0

    enable_dns: bool = True
    enable_geoip: bool = True
    enable_alive: bool = False  # ping полностью вырубаем

    db_dir: str = "data"
    country_db_filename: str = "GeoLite2-Country.mmdb"
    asn_db_filename: str = "GeoLite2-ASN.mmdb"

    country_db_url: str = ""
    asn_db_url: str = ""

    max_nodes_per_run: int = 5000  # обрабатываем только первые 5000
    ping_timeout: float = 0.5


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
            if self.country_db_path.exists():
                try:
                    self._geo_country = geoip2.database.Reader(str(self.country_db_path))
                except Exception:
                    self._geo_country = None

            if self.asn_db_path.exists():
                try:
                    self._geo_asn = geoip2.database.Reader(str(self.asn_db_path))
                except Exception:
                    self._geo_asn = None

    def enrich_all(self, nodes: List[VPNNode]) -> None:
        max_n = min(self.config.max_nodes_per_run or len(nodes), len(nodes))
        for i, node in enumerate(nodes[:max_n]):
            self._enrich_node(node)
        if self.debug:
            print(f"      [Enricher] processed {max_n} nodes out of {len(nodes)}")

    def _enrich_node(self, node: VPNNode) -> None:
        extra = node.extra

        if self.config.enable_dns and "ip" not in extra:
            ip = self._resolve_ip(node.host)
            if ip:
                extra["ip"] = ip
                if self.debug:
                    print(f"      [DNS] {node.host} -> {ip}")

        ip = extra.get("ip")
        if not ip:
            return

        if self.config.enable_geoip:
            if self._geo_country:
                try:
                    c = self._geo_country.country(ip)
                    extra["country"] = c.country.iso_code
                except Exception:
                    pass

            if self._geo_asn:
                try:
                    a = self._geo_asn.asn(ip)
                    extra["asn"] = a.autonomous_system_number
                    extra["asn_name"] = a.autonomous_system_organization
                except Exception:
                    pass

        # ping отключён (enable_alive=False)

    def _resolve_ip(self, host: str) -> Optional[str]:
        try:
            return socket.gethostbyname(host)
        except Exception:
            return None

    def _tcp_ping(self, host: str, port: int, timeout: float = 0.5) -> Optional[float]:
        try:
            start = time.monotonic()
            with socket.create_connection((host, port), timeout=timeout):
                end = time.monotonic()
            return (end - start) * 1000.0
        except Exception:
            return None
