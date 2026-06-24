"""Tests for the Qdrant memory store and Incident model."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore


class TestIncident:

    def test_to_payload(self):
        inc = Incident(
            id="i1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc123",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web container exited",
            llm_analysis="Out of memory",
        )
        payload = inc.to_payload()
        assert payload["id"] == "i1"
        assert payload["event_type"] == "crash"
        assert payload["llm_analysis"] == "Out of memory"

    def test_to_payload_no_analysis(self):
        inc = Incident(
            id="i2",
            timestamp="2026-01-01T00:00:00Z",
            container_id="def456",
            container_name="db",
            event_type="state_change",
            severity="info",
            message="state changed",
        )
        payload = inc.to_payload()
        assert payload["llm_analysis"] is None

    def test_from_payload(self):
        payload = {
            "id": "i3",
            "timestamp": "2026-01-01T00:00:00Z",
            "container_id": "ghi789",
            "container_name": "api",
            "event_type": "threshold",
            "severity": "warning",
            "message": "cpu high",
            "llm_analysis": "Load spike",
        }
        inc = Incident.from_payload(payload)
        assert inc.id == "i3"
        assert inc.llm_analysis == "Load spike"

    def test_roundtrip(self):
        original = Incident(
            id="i4",
            timestamp="2026-01-01T00:00:00Z",
            container_id="xyz999",
            container_name="worker",
            event_type="crash",
            severity="critical",
            message="crashed",
        )
        roundtrip = Incident.from_payload(original.to_payload())
        assert roundtrip == original

    def test_dataclass_equality(self):
        a = Incident(id="x", timestamp="t", container_id="c", container_name="n",
                     event_type="e", severity="s", message="m")
        b = Incident(id="x", timestamp="t", container_id="c", container_name="n",
                     event_type="e", severity="s", message="m")
        assert a == b

    def test_dataclass_inequality(self):
        a = Incident(id="x", timestamp="t", container_id="c", container_name="n",
                     event_type="e", severity="s", message="m")
        b = Incident(id="y", timestamp="t", container_id="c", container_name="n",
                     event_type="e", severity="s", message="m")
        assert a != b


class TestQdrantMemoryStore:

    @pytest.fixture
    def mock_qdrant_client(self):
        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        return client

    @pytest.fixture
    def store(self, config, mock_qdrant_client):
        return QdrantMemoryStore(config, client=mock_qdrant_client)

    # -- Connection --

    def test_connect(self, store, mock_qdrant_client):
        store.connect()
        assert store._initialized is True
        mock_qdrant_client.get_collections.assert_called()

    def test_connect_creates_collection(self, store, mock_qdrant_client):
        store.connect()
        mock_qdrant_client.create_collection.assert_called_once()

    def test_connect_skips_existing_collection(self, config, mock_qdrant_client):
        mock_coll = MagicMock()
        mock_coll.name = "infra_events"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[mock_coll]
        )
        store = QdrantMemoryStore(config, client=mock_qdrant_client)
        store.connect()
        mock_qdrant_client.create_collection.assert_not_called()

    def test_connect_raises_on_failure(self, config, mock_qdrant_client):
        mock_qdrant_client.get_collections.side_effect = ConnectionError("refused")
        store = QdrantMemoryStore(config, client=mock_qdrant_client)
        with pytest.raises(ConnectionError):
            store.connect()

    def test_lazy_connect_on_store(self, store, mock_qdrant_client):
        inc = Incident(
            id="i1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web crash",
        )
        store.store_incident(inc)
        assert store._initialized is True

    # -- Write --

    def test_store_incident(self, store, mock_qdrant_client):
        inc = Incident(
            id="i1",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="crash",
            severity="critical",
            message="web crash",
        )
        store.store_incident(inc, vector=[0.5] * 1536)
        mock_qdrant_client.upsert.assert_called_once()

    def test_store_incident_default_vector(self, store, mock_qdrant_client):
        inc = Incident(
            id="i2",
            timestamp="2026-01-01T00:00:00Z",
            container_id="abc",
            container_name="web",
            event_type="state_change",
            severity="info",
            message="changed",
        )
        store.store_incident(inc)
        call_args = mock_qdrant_client.upsert.call_args
        point = call_args[1]["points"][0]
        assert point.vector == [0.0] * 1536

    # -- Read --

    def test_get_incident(self, store, mock_qdrant_client):
        mock_payload = MagicMock()
        mock_payload.payload = {
            "id": "i1",
            "timestamp": "2026-01-01T00:00:00Z",
            "container_id": "abc",
            "container_name": "web",
            "event_type": "crash",
            "severity": "critical",
            "message": "web crash",
        }
        mock_qdrant_client.retrieve.return_value = [mock_payload]

        result = store.get_incident("i1")
        assert result.id == "i1"
        assert result.container_name == "web"

    def test_get_incident_not_found(self, store, mock_qdrant_client):
        mock_qdrant_client.retrieve.return_value = []
        result = store.get_incident("missing")
        assert result is None

    def test_search_similar(self, store, mock_qdrant_client):
        mock_result = MagicMock()
        mock_result.payload = {
            "id": "s1",
            "timestamp": "2026-01-01T00:00:00Z",
            "container_id": "abc",
            "container_name": "web",
            "event_type": "crash",
            "severity": "critical",
            "message": "crash",
        }
        mock_qdrant_client.query_points.return_value = MagicMock(points=[mock_result])

        results = store.search_similar([0.1] * 1536)
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_get_all(self, store, mock_qdrant_client):
        mock_point = MagicMock()
        mock_point.payload = {
            "id": "a1",
            "timestamp": "2026-01-01T00:00:00Z",
            "container_id": "abc",
            "container_name": "web",
            "event_type": "crash",
            "severity": "critical",
            "message": "crash",
        }
        mock_qdrant_client.scroll.return_value = ([mock_point], None)

        results = store.get_all()
        assert len(results) == 1
        assert results[0].id == "a1"

    def test_count(self, store, mock_qdrant_client):
        mock_info = MagicMock()
        mock_info.vectors_count = 42
        mock_qdrant_client.get_collection.return_value = mock_info
        assert store.count() == 42

    def test_count_no_vectors_attr(self, store, mock_qdrant_client):
        class MinimalInfo:
            """Object without vectors_count attribute."""
            pass
        mock_qdrant_client.get_collection.return_value = MinimalInfo()
        assert store.count() == 0

    # -- Delete --

    def test_delete_incident(self, store, mock_qdrant_client):
        assert store.delete_incident("i1") is True
        mock_qdrant_client.delete.assert_called_once()

    def test_delete_incident_raises(self, store, mock_qdrant_client):
        mock_qdrant_client.delete.side_effect = Exception("error")
        assert store.delete_incident("i1") is False
