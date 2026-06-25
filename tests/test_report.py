"""Tests for report/generator.py."""

import json

from infra_agent_v2.config import Config
from infra_agent_v2.report.generator import (
    ReportGenerator,
    ReportStats,
    Report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_incidents():
    return [
        {
            "timestamp": "2026-01-01T10:00:00+00:00",
            "container_id": "c1",
            "container_name": "web",
            "event_type": "crash",
            "severity": "critical",
            "message": "OOMKilled",
            "llm_analysis": "Memory leak in web service",
        },
        {
            "timestamp": "2026-01-01T09:00:00+00:00",
            "container_id": "c2",
            "container_name": "db",
            "event_type": "restart",
            "severity": "warning",
            "message": "Container restarted",
            "llm_analysis": None,
        },
        {
            "timestamp": "2026-01-01T08:00:00+00:00",
            "container_id": "c3",
            "container_name": "cache",
            "event_type": "state_change",
            "severity": "info",
            "message": "Container started",
            "llm_analysis": None,
        },
    ]

# ---------------------------------------------------------------------------
# ReportStats
# ---------------------------------------------------------------------------

class TestReportStats:
    """ReportStats dataclass."""

    def test_defaults(self):
        stats = ReportStats()
        assert stats.total_incidents == 0
        assert stats.critical_count == 0
        assert stats.warning_count == 0
        assert stats.info_count == 0
        assert stats.by_type == {}
        assert stats.by_container == {}

    def test_populated(self):
        stats = ReportStats(
            total_incidents=5,
            critical_count=2,
            warning_count=2,
            info_count=1,
            by_type={"crash": 2, "restart": 3},
            by_container={"web": 3, "db": 2},
        )
        assert stats.critical_count == 2
        assert stats.by_type["crash"] == 2

# ---------------------------------------------------------------------------
# Stats Computation
# ---------------------------------------------------------------------------

class TestReportGeneratorStats:
    """Stats computation from incidents."""

    def test_compute_stats(self, config):
        incidents = _sample_incidents()
        stats = ReportGenerator(config)._compute_stats(incidents)
        assert stats.total_incidents == 3
        assert stats.critical_count == 1
        assert stats.warning_count == 1
        assert stats.info_count == 1

    def test_compute_stats_by_type(self, config):
        incidents = _sample_incidents()
        stats = ReportGenerator(config)._compute_stats(incidents)
        assert stats.by_type["crash"] == 1
        assert stats.by_type["restart"] == 1
        assert stats.by_type["state_change"] == 1

    def test_compute_stats_by_container(self, config):
        incidents = _sample_incidents()
        stats = ReportGenerator(config)._compute_stats(incidents)
        assert stats.by_container["web"] == 1
        assert stats.by_container["db"] == 1
        assert stats.by_container["cache"] == 1

    def test_compute_stats_empty(self, config):
        stats = ReportGenerator(config)._compute_stats([])
        assert stats.total_incidents == 0

# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestReportGeneratorSort:
    """Incident sorting by severity and timestamp."""

    def test_sort_critical_first(self, config):
        incidents = _sample_incidents()
        sorted_ = ReportGenerator(config)._sort_incidents(incidents)
        assert sorted_[0]["severity"] == "critical"

    def test_sort_warning_before_info(self, config):
        incidents = _sample_incidents()
        sorted_ = ReportGenerator(config)._sort_incidents(incidents)
        assert sorted_[1]["severity"] == "warning"
        assert sorted_[2]["severity"] == "info"

# ---------------------------------------------------------------------------
# Full Report Generation
# ---------------------------------------------------------------------------

class TestReportGeneratorFull:
    """Full report generation."""

    def test_generate_returns_report(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents)
        assert isinstance(report, Report)
        assert report.title == "Incident Report"
        assert report.stats.total_incidents == 3

    def test_generate_with_custom_title(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents, title="My Report")
        assert report.title == "My Report"

    def test_generate_includes_llm_analysis(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents)
        assert "Memory leak" in report.text

    def test_generate_json(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents, include_json=True)
        data = json.loads(report.json_str)
        assert data["title"] == "Incident Report"
        assert data["stats"]["total_incidents"] == 3

    def test_generate_text_only(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents, include_text=True, include_json=False)
        assert report.text
        assert not report.json_str

    def test_generate_json_only(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        report = gen.generate(incidents, include_text=False, include_json=True)
        assert not report.text
        assert report.json_str

# ---------------------------------------------------------------------------
# Convenience Methods
# ---------------------------------------------------------------------------

class TestReportGeneratorConvenience:
    """generate_text and generate_json methods."""

    def test_generate_text(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "Incident Report" in text
        assert "OOMKilled" in text

    def test_generate_json(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        j = gen.generate_json(incidents)
        data = json.loads(j)
        assert "stats" in data
        assert "incidents" in data

# ---------------------------------------------------------------------------
# Text Report Content
# ---------------------------------------------------------------------------

class TestReportTextContent:
    """Text report formatting."""

    def test_text_includes_summary(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "--- Summary ---" in text
        assert "--- Incidents ---" in text

    def test_text_includes_severity_counts(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "Critical: 1" in text
        assert "Warning: 1" in text
        assert "Info: 1" in text

    def test_text_includes_by_type(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "--- By Event Type ---" in text

    def test_text_includes_by_container(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "--- By Container ---" in text

    def test_text_includes_incident_entries(self, config):
        incidents = _sample_incidents()
        gen = ReportGenerator(config)
        text = gen.generate_text(incidents)
        assert "[1]" in text
        assert "[2]" in text
        assert "[3]" in text
