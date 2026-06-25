"""Tests for llm/analyzer.py."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.llm.analyzer import (
    IncidentAnalyzer,
    AnalysisResult,
)
from infra_agent_v2.llm.client import LLMClient
from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    """Return a mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.chat.return_value = "warning"
    client.generate_embedding.return_value = [0.1] * 1536
    client.generate_embeddings_batch.return_value = [[0.1] * 1536]
    return client

@pytest.fixture
def mock_store():
    """Return a mock QdrantMemoryStore."""
    store = MagicMock(spec=QdrantMemoryStore)
    store.search_similar.return_value = []
    return store

@pytest.fixture
def analyzer(config, mock_llm, mock_store):
    """Return an IncidentAnalyzer with mocked dependencies."""
    return IncidentAnalyzer(config, llm_client=mock_llm, memory_store=mock_store)

# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------

class TestAnalysisResult:
    """AnalysisResult dataclass behavior."""

    def test_defaults(self):
        result = AnalysisResult(
            incident=Incident(
                id="abc",
                timestamp="2026-01-01T00:00:00+00:00",
                container_id="c1",
                container_name="web",
                event_type="crash",
                severity="critical",
                message="OOMKilled",
            ),
            severity="critical",
        )
        assert result.severity == "critical"
        assert result.similar_incidents == []

    def test_with_similar(self):
        similar = [
            Incident(
                id="prev1",
                timestamp="2026-01-01T00:00:00+00:00",
                container_id="c2",
                container_name="web",
                event_type="crash",
                severity="critical",
                message="OOMKilled earlier",
            ),
        ]
        result = AnalysisResult(
            incident=Incident(
                id="abc",
                timestamp="2026-01-01T00:00:00+00:00",
                container_id="c1",
                container_name="web",
                event_type="crash",
                severity="critical",
                message="OOMKilled",
            ),
            severity="critical",
            similar_incidents=similar,
        )
        assert len(result.similar_incidents) == 1

# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerPipeline:
    """Full analyze() pipeline."""

    def test_analyze_returns_result(self, analyzer, mock_llm, mock_store):
        mock_llm.chat.side_effect = ["warning", "Root cause: memory leak"]
        result = analyzer.analyze(
            event_type="crash",
            container_name="web",
            message="OOMKilled",
        )
        assert isinstance(result, AnalysisResult)
        assert result.severity == "warning"
        assert result.incident.llm_analysis == "Root cause: memory leak"

    def test_analyze_stores_incident(self, analyzer, mock_store):
        analyzer.analyze("crash", "web", "OOMKilled")
        assert mock_store.store_incident.call_count == 1
        incident = mock_store.store_incident.call_args[0][0]
        assert incident.container_name == "web"

    def test_analyze_searches_similar(self, analyzer, mock_store):
        analyzer.analyze("crash", "web", "OOMKilled")
        assert mock_store.search_similar.call_count == 1

    def test_analyze_with_container_id(self, analyzer):
        result = analyzer.analyze("crash", "web", "OOMKilled", container_id="abc123")
        assert result.incident.container_id == "abc123"

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerClassification:
    """Severity classification."""

    def test_classify_returns_valid_severity(self, analyzer, mock_llm):
        mock_llm.chat.return_value = "critical"
        result = analyzer.classify("crash", "web", "OOMKilled")
        assert result == "critical"

    def test_classify_falls_back_on_llm_error(self, analyzer, mock_llm):
        mock_llm.chat.side_effect = RuntimeError("timeout")
        result = analyzer.classify("restart", "web", "unhealthy")
        assert result == "warning"  # heuristic

    def test_classify_ignores_bad_llm_output(self, analyzer, mock_llm):
        mock_llm.chat.return_value = "severe"
        result = analyzer.classify("restart", "web", "unhealthy")
        assert result == "warning"  # fallback

    def test_heuristic_crash_is_critical(self):
        severity = IncidentAnalyzer._heuristic_severity("crash", "OOMKilled")
        assert severity == "critical"

    def test_heuristic_oom_is_critical(self):
        severity = IncidentAnalyzer._heuristic_severity("state_change", "Container OOM killed")
        assert severity == "critical"

    def test_heuristic_restart_is_warning(self):
        severity = IncidentAnalyzer._heuristic_severity("restart", "container unhealthy")
        assert severity == "warning"

    def test_heuristic_default_is_info(self):
        severity = IncidentAnalyzer._heuristic_severity("state_change", "container started")
        assert severity == "info"

# ---------------------------------------------------------------------------
# Root Cause Analysis
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerRootCause:
    """Root-cause analysis."""

    def test_root_cause_returns_llm_output(self, analyzer, mock_llm):
        mock_llm.chat.return_value = "Root cause: memory leak in web service"
        result = analyzer.analyze_root_cause("crash", "web", "OOMKilled", "critical")
        assert "memory leak" in result

    def test_root_cause_falls_back_on_llm_error(self, analyzer, mock_llm):
        mock_llm.chat.side_effect = RuntimeError("timeout")
        result = analyzer.analyze_root_cause("crash", "web", "OOMKilled", "critical")
        assert "web" in result
        assert "crash" in result

# ---------------------------------------------------------------------------
# Similar Incident Search
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerSimilar:
    """Similar incident search."""

    def test_get_similar_returns_incidents(self, analyzer, mock_store):
        prev = Incident(
            id="prev",
            timestamp="2026-01-01T00:00:00+00:00",
            container_id="c1",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="OOMKilled before",
        )
        mock_store.search_similar.return_value = [prev]
        results = analyzer.get_similar("OOMKilled")
        assert len(results) == 1
        assert results[0].message == "OOMKilled before"

    def test_get_similar_falls_back_on_store_error(self, analyzer, mock_store):
        mock_store.search_similar.side_effect = RuntimeError("connection lost")
        results = analyzer.get_similar("OOMKilled")
        assert results == []

# ---------------------------------------------------------------------------
# Embedding Fallback
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerEmbedding:
    """Embedding generation and fallback."""

    def test_embed_uses_llm(self, analyzer, mock_llm):
        mock_llm.generate_embedding.return_value = [0.5] * 1536
        result = analyzer._embed_text("OOMKilled")
        assert len(result) == 1536
        assert result[0] == 0.5

    def test_embed_falls_back_on_llm_error(self, analyzer, mock_llm):
        mock_llm.generate_embedding.side_effect = RuntimeError("timeout")
        result = analyzer._embed_text("OOMKilled")
        assert len(result) == 1536
        assert all(v == 0.0 for v in result)

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestIncidentAnalyzerInit:
    """Analyzer initialization."""

    def test_init_with_deps(self, config, mock_llm, mock_store):
        analyzer = IncidentAnalyzer(config, llm_client=mock_llm, memory_store=mock_store)
        assert analyzer.llm is mock_llm
        assert analyzer.store is mock_store

    def test_init_without_deps(self, config, monkeypatch):
        # Should not raise; deps are built internally
        with patch.object(LLMClient, "__init__", return_value=None):
            with patch.object(QdrantMemoryStore, "__init__", return_value=None):
                analyzer = IncidentAnalyzer(config)
                assert analyzer.llm is not None
                assert analyzer.store is not None
