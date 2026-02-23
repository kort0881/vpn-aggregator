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
        lines = []

        lines.append(f"# VPN Aggregator Report")
        lines.append("")
        lines.append(f"- Generated at: **{ts}**")
        lines.append(f"- Raw nodes (lines before parse): **{nodes_raw}**")
        lines.append(f"- Final nodes after filters: **{len(nodes_final)}**")
        lines.append("")

        lines.append("## Filter stats")
        lines.append("")
        lines.append(f"- Before: `{filter_stats.get('before')}`")
        lines.append(f"- Dropped as duplicates: `{filter_stats.get('dropped_dup')}`")
        lines.append(f"- Dropped by filters: `{filter_stats.get('dropped_filter')}`")
        lines.append(f"- After: `{filter_stats.get('after')}`")
        lines.append("")

        lines.append("## Sources")
        lines.append("")
        if not source_profiles:
            lines.append("_No profiles available_")
        else:
            lines.append("| Source | Nodes | Avg ping | Unique ASNs | Quality |")
            lines.append("|--------|-------|----------|-------------|---------|")
            for name, p in sorted(source_profiles.items()):
                lines.append(
                    f"| `{name}` | {p.get('nodes')} | "
                    f"{p.get('avg_ping') or '-'} | "
                    f"{p.get('asn_unique') or '-'} | "
                    f"{p.get('quality')} |"
                )

        report = "\n".join(lines) + "\n"
        self.out_path.write_text(report, encoding="utf-8")
        return report
