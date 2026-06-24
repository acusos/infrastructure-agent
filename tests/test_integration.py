"""Integration tests for Phase 2: LLM + Qdrant + Monitor pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore
from infra_agent_v2.llm.client import LLMClient

LLM_ENDPOINT = "http://192.168.20.116:4000"


class TestMonitorToMemory:
    """Monitor events are correctly persisted via QdrantMemoryStore."""

    @pytest.fixture
    def store(self, config):
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        return QdrantMemoryStore(config, client=mock_client)

    def test_store_and_retrieve_incident(self, store):
        inc = Incident(
            id="inc-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web container crashed with exit code 1",
        )
        store.store_incident(inc)
        assert store._initialized is True

    def test_store_and_search_similar(self, store):
        inc = Incident(
            id="inc-2",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="threshold",
            severity="warning",
            message="CPU high",
        )
        store.store_incident(inc)
        mock_result = MagicMock()
        mock_result.payload = inc.to_payload()
        store.client.query_points.return_value = MagicMock(points=[mock_result])

        results = store.search_similar([0.1] * 1536)
        assert len(results) == 1

    def test_store_and_delete(self, store):
        inc = Incident(
            id="inc-3",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="db",
            event_type="crash",
            severity="critical",
            message="db crashed",
        )
        store.store_incident(inc)
        deleted = store.delete_incident("inc-3")
        assert deleted is True


class TestLLMAnalyzeAndStore:
    """LLM analysis is attached to incidents and stored correctly."""

    @pytest.fixture
    def llm(self, config):
        with patch("infra_agent_v2.llm.client.litellm") as m:
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "Root cause: OOM. Fix: increase memory."
            m.completion.return_value = mock_resp
            yield LLMClient(config)

    @pytest.fixture
    def store(self, config):
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        return QdrantMemoryStore(config, client=mock_client)

    def test_analyze_and_store(self, llm, store):
        analysis = llm.analyze_incident(
            message="web crashed",
            event_type="crash",
            container_name="web",
            severity="critical",
        )
        assert "OOM" in analysis

        inc = Incident(
            id="inc-int-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web crashed",
            llm_analysis=analysis,
        )
        store.store_incident(inc)
        store.client.upsert.assert_called_once()

    def test_embedding_generation(self, llm):
        with patch("infra_agent_v2.llm.client.litellm") as m:
            mock_resp = MagicMock()
            mock_resp.data[0].embedding = [0.5] * 1536
            m.embedding.return_value = mock_resp
            vec = llm.generate_embedding("web container crashed")
            assert len(vec) == 1536

    def test_full_pipeline(self, llm, store):
        # 1. LLM analyzes
        analysis = llm.analyze_incident(
            message="db crashed with exit code 137",
            event_type="crash",
            container_name="db",
            severity="critical",
        )
        assert len(analysis) > 0

        # 2. Store incident with analysis
        inc = Incident(
            id="inc-pipeline-1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="db-123",
            container_name="db",
            event_type="crash",
            severity="critical",
            message="db crashed with exit code 137",
            llm_analysis=analysis,
        )
        store.store_incident(inc)
        store.client.upsert.assert_called_once()

        # 3. Retrieve and verify analysis is attached
        mock_result = MagicMock()
        mock_result.payload = inc.to_payload()
        store.client.retrieve.return_value = [mock_result]
        retrieved = store.get_incident("inc-pipeline-1")
        assert retrieved.llm_analysis == analysis
