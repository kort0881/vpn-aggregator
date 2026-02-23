"""
Reporter:
- собирает markdown-отчёт по пайплайну
- сохраняет в sources_meta/pipeline_report.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .parser import VPNNode


class Reporter:
    def __init__(self, out_path: str = "sources_meta/pipeline_report.md"):
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        nodes_raw: int,
        nodes_final: List[VPNNode],
        filter_stats: Dict,
        source_profiles: Dict[str, Dict],
    ) -> str:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        lines: List[str] = []

        lines.append("# VPN Aggregator Report")
        lines.append("")
        lines.append(f"- Generated at: **{ts}**")
        lines.append(f"- Raw nodes (lines before parse): **{nodes_raw}**")
        lines.append(f"- Final nodes after filters: **{len(nodes_final)}**")
        lines.append("")

        # Filter stats
        lines.append("## Filter stats")
        lines.append("")
        lines.append(f"- Before: `{filter_stats.get('before')}`")
        lines.append(f"- Dropped as duplicates: `{filter_stats.get('dropped_dup')}`")
        lines.append(f"- Dropped by filters: `{filter_stats.get('dropped_filter')}`")
        lines.append(f"- After: `{filter_stats.get('after')}`")
        lines.append("")

        # Sources table
        lines.append("## Sources")
        lines.append("")
        if not source_profiles:
            lines.append("_No profiles available_")
        else:
            lines.append(
                "| Source | Nodes | EU share | Bad country share | "
                "Avg ping | Alive ratio | Unique IPs |"
            )
            lines.append(
                "|--------|-------|----------|-------------------|"
                "----------|-------------|-----------|"
            )
            for name, p in sorted(source_profiles.items()):
                nodes = p.get("total_nodes") or p.get("nodes")
                eu_share = p.get("eu_share")
                bad_share = p.get("bad_country_share")
                avg_ping = p.get("avg_ping")
                alive_ratio = p.get("alive_ratio")
                unique_ips = p.get("unique_ips")

                def fmt_ratio(x):
                    if x is None:
                        return "-"
                    return f"{x:.2f}"

                lines.append(
                    f"| `{name}` | {nodes} | "
                    f"{fmt_ratio(eu_share)} | "
                    f"{fmt_ratio(bad_share)} | "
                    f"{avg_ping if avg_ping is not None else '-'} | "
                    f"{fmt_ratio(alive_ratio)} | "
                    f"{unique_ips if unique_ips is not None else '-'} |"
                )

        report = "\n".join(lines) + "\n"
        self.out_path.write_text(report, encoding="utf-8")
        return report
