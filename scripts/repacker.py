from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import List, Dict

from .parser import VPNNode


class Repacker:
    def __init__(self, config: dict):
        self.config = config
        out_cfg = self.config.get("output", {}) or {}
        base_out = Path(out_cfg.get("base_path", "./out"))
        self.by_type_dir = base_out / "by_type"
        self.by_country_dir = base_out / "by_country"
        self.subs_dir = base_out / "subs"

        self.by_type_dir.mkdir(parents=True, exist_ok=True)
        self.by_country_dir.mkdir(parents=True, exist_ok=True)
        self.subs_dir.mkdir(parents=True, exist_ok=True)

    def repack(self, nodes: List[VPNNode]) -> None:
        # Группировка по типу и стране
        by_type: Dict[str, List[str]] = defaultdict(list)
        by_country: Dict[str, List[str]] = defaultdict(list)

        for node in nodes:
            uri = node.to_uri()  # предполагаем, что VPNNode умеет собирать URI
            t = node.protocol     # 'vless' / 'vmess' / 'ss'
            by_type[t].append(uri)

            extra = node.extra or {}
            country = extra.get("country") or "XX"
            by_country[country].append(uri)

        # Запись по типам
        for t, lines in by_type.items():
            path = self.by_type_dir / f"{t}.txt"
            text = "\n".join(lines) + "\n"
            path.write_text(text, encoding="utf-8")
            print(f"    - by_type: {t} -> {path} ({len(lines)} lines)")

        # Запись по странам
        for country, lines in by_country.items():
            path = self.by_country_dir / f"{country}.txt"
            text = "\n".join(lines) + "\n"
            path.write_text(text, encoding="utf-8")
            print(f"    - by_country: {country} -> {path} ({len(lines)} lines)")

        # Саб-генерация
        for t, lines in by_type.items():
            sub_path = self.subs_dir / f"{t}_sub.txt"
            text = "\n".join(lines) + "\n"
            sub_path.write_text(text, encoding="utf-8")
            print(f"    - sub: {t} -> {sub_path} ({len(lines)} lines)")
