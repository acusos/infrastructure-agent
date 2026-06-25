"""Report generator for Infra Agent v2.

Generates structured incident reports from a list of incidents, with support
for both JSON and plain-text output formats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.report")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ReportStats:
    """Summary statistics for a report."""
    total_incidents: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_container: Dict[str, int] = field(default_factory=dict)

@dataclass
class Report:
    """A generated incident report."""
    timestamp: str
    title: str
    stats: ReportStats
    incidents: List[dict]
    text: str = ""
    json_str: str = ""

# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates structured incident reports."""

    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    def __init__(self, config: Config):
        self.config = config

    def generate(
        self,
        incidents: List[dict],
        title: str = "Incident Report",
        include_text: bool = True,
        include_json: bool = False,
    ) -> Report:
        """Generate a report from a list of incident dicts.

        Args:
            incidents: List of incident dicts with keys: timestamp, container_id,
                       container_name, event_type, severity, message, llm_analysis.
            title: Report title.
            include_text: Include formatted plain-text in the Report.
            include_json: Include serialized JSON in the Report.

        Returns:
            A Report object with stats, text, and/or JSON.
        """
        stats = self._compute_stats(incidents)
        sorted_incidents = self._sort_incidents(incidents)

        text = self._format_text(title, stats, sorted_incidents) if include_text else ""
        json_str = self._serialize(title, stats, sorted_incidents) if include_json else ""

        return Report(
            timestamp=datetime.now(timezone.utc).isoformat(),
            title=title,
            stats=stats,
            incidents=sorted_incidents,
            text=text,
            json_str=json_str,
        )

    def generate_text(self, incidents: List[dict],
                       title: str = "Incident Report") -> str:
        """Return only the plain-text report."""
        return self.generate(incidents, title=title,
                             include_text=True, include_json=False).text

    def generate_json(self, incidents: List[dict],
                       title: str = "Incident Report") -> str:
        """Return only the JSON report."""
        return self.generate(incidents, title=title,
                             include_text=False, include_json=True).json_str

    # -- Internal --

    @classmethod
    def _compute_stats(cls, incidents: List[dict]) -> ReportStats:
        stats = ReportStats(total_incidents=len(incidents))
        for inc in incidents:
            sev = inc.get("severity", "info")
            if sev == "critical":
                stats.critical_count += 1
            elif sev == "warning":
                stats.warning_count += 1
            else:
                stats.info_count += 1

            etype = inc.get("event_type", "unknown")
            stats.by_type[etype] = stats.by_type.get(etype, 0) + 1

            cname = inc.get("container_name", inc.get("container_id", "unknown"))
            stats.by_container[cname] = stats.by_container.get(cname, 0) + 1
        return stats

    @classmethod
    def _sort_incidents(cls, incidents: List[dict]) -> List[dict]:
        """Sort incidents by severity (critical first) then by timestamp (newest first)."""
        return sorted(
            incidents,
            key=lambda x: (
                cls.SEVERITY_ORDER.get(x.get("severity", "info"), 9),
                x.get("timestamp", ""),
            ),
        )

    @staticmethod
    def _format_text(title: str, stats: ReportStats,
                     incidents: List[dict]) -> str:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  {title}")
        lines.append(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("=" * 60)
        lines.append("")
        lines.append("--- Summary ---")
        lines.append(f"  Total incidents: {stats.total_incidents}")
        lines.append(f"  Critical: {stats.critical_count}  |  Warning: {stats.warning_count}  |  Info: {stats.info_count}")
        lines.append("")

        if stats.by_type:
            lines.append("--- By Event Type ---")
            for etype, count in sorted(stats.by_type.items(), key=lambda x: -x[1]):
                lines.append(f"  {etype}: {count}")
            lines.append("")

        if stats.by_container:
            lines.append("--- By Container ---")
            for cname, count in sorted(stats.by_container.items(), key=lambda x: -x[1]):
                lines.append(f"  {cname}: {count}")
            lines.append("")

        lines.append("--- Incidents ---")
        for i, inc in enumerate(incidents, 1):
            lines.append(f"\n  [{i}] {inc.get('severity', 'info').upper()} — {inc.get('event_type', 'unknown')}")
            lines.append(f"      Container: {inc.get('container_name', inc.get('container_id', '?'))}")
            lines.append(f"      Time:      {inc.get('timestamp', '?')}")
            lines.append(f"      Message:   {inc.get('message', '?')}")
            if inc.get("llm_analysis"):
                lines.append(f"      Analysis:  {inc['llm_analysis']}")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _serialize(title: str, stats: ReportStats,
                    incidents: List[dict]) -> str:
        """Serialize report to JSON."""
        return json.dumps({
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_incidents": stats.total_incidents,
                "critical_count": stats.critical_count,
                "warning_count": stats.warning_count,
                "info_count": stats.info_count,
                "by_type": stats.by_type,
                "by_container": stats.by_container,
            },
            "incidents": incidents,
        }, indent=2)
