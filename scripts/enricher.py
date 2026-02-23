"""
Enricher:
- DNS resolve (host -> ip)
- GeoIP (country, asn) — пока заглушка
- Alive/ping — пока заглушка
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import List, Optional

from .parser import VPNNode


@dataclass
class EnricherConfig:
    dns_timeout: float = 2.0
    enable_dns: bool = True
    enable_geoip: bool = False   # включишь, когда прикрутишь geoip2
    enable_alive: bool = False   # включишь, когда прикрутишь проверку живости


class Enricher:
    def __init__(self, config: Optional[EnricherConfig] = None, debug: bool = False):
        self.config = config or EnricherConfig()
        self.debug = debug

    def enrich_all(self, nodes: List[VPNNode]) -> None:
        for node in nodes:
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

        # GeoIP (пока заглушка)
        if self.config.enable_geoip:
            # TODO: здесь можешь позже использовать geoip2 / maxminddb
            ip = extra.get("ip")
            if ip:
                # заглушка: просто помечаем как "XX"
                extra.setdefault("country", "XX")
                extra.setdefault("asn", 0)

        # Alive/ping (пока заглушка)
        if self.config.enable_alive:
            extra.setdefault("alive", True)
            extra.setdefault("ping", 0)

    def _resolve_ip(self, host: str) -> Optional[str]:
        try:
            return socket.gethostbyname(host)
        except Exception:
            return None
