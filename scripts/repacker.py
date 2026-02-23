"""
Repacker:
- применяет шаблон remark/branding
- rebuild URI через ConfigParser.rebuild_uri
- раскладывает по out/by_type и out/by_country
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .parser import VPNNode, ConfigParser


class Repacker:
    def __init__(self, config: Dict):
        self.config = config or {}
        out_cfg = self.config.get("output", {}) or {}

        self.base_out = Path(out_cfg.get("base_path", "./out"))
        self.format_template = out_cfg.get(
            "format_template", "{country} {ping}ms AS{asn} {protocol}"
        )
        self.split_by_country = out_cfg.get("split_by_country", True)
        self.split_by_type = out_cfg.get("split_by_type", True)

        repack_cfg = out_cfg.get("repack", {}) or {}
        self.preserve_fields = repack_cfg.get(
            "preserve_fields", ["uuid", "password", "port", "host"]
        )

    def repack(self, nodes: List[VPNNode]) -> None:
        if not nodes:
            print("    ! Repacker: no nodes to repack")
            return

        by_type_dir = self.base_out / "by_type"
        by_country_dir = self.base_out / "by_country"
        by_type_dir.mkdir(parents=True, exist_ok=True)
        by_country_dir.mkdir(parents=True, exist_ok=True)

        # Списки URI (финальный вид, пригодный для сабов)
        uris_by_type: Dict[str, List[str]] = {}
        uris_by_country: Dict[str, List[str]] = {}

        for node in nodes:
            proto = node.protocol or "unknown"
            extra = node.extra
            country = extra.get("country", "XX")
            ping = extra.get("ping", 0)
            asn = extra.get("asn", 0)

            # remark по шаблону
            remark = self.format_template.format(
                country=country,
                ping=ping,
                asn=asn,
                protocol=proto,
            )

            # rebuild URI с новым remark
            uri = ConfigParser.rebuild_uri(node, new_remark=remark)

            if self.split_by_type:
                uris_by_type.setdefault(proto, []).append(uri)
            if self.split_by_country:
                uris_by_country.setdefault(country, []).append(uri)

        # Запись по типам
        if self.split_by_type:
            for proto, uris in uris_by_type.items():
                path = by_type_dir / f"{proto}.txt"
                path.write_text("\n".join(uris) + "\n", encoding="utf-8")
                print(f"    - by_type: {proto} -> {path} ({len(uris)} lines)")

        # Запись по странам
        if self.split_by_country:
            for country, uris in uris_by_country.items():
                path = by_country_dir / f"{country}.txt"
                path.write_text("\n".join(uris) + "\n", encoding="utf-8")
                print(f"    - by_country: {country} -> {path} ({len(uris)} lines)")
