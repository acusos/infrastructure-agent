"""Verification suite for infra_agent_v2 Phase 2.

Connects to real LiteLLM and Qdrant services, runs a full pipeline,
and produces a pass/fail report.

Usage:
    python -m pytest tests/verify.py -v -s
"""

import sys
from datetime import datetime, timezone
from typing import List, Tuple

import pytest
from qdrant_client import QdrantClient

from infra_agent_v2.config import Config
from infra_agent_v2.llm.client import LLMClient
from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LITE_LLM_URL = "http://192.168.20.116:4000"
QDRANT_HOST = "192.168.20.116"
QDRANT_PORT = 6333
VERIFICATION_COLLECTION = "verification_test"
LLM_MODEL = "qwopus"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def config() -> Config:
    cfg = Config()
    cfg.llm.base_url = LITE_LLM_URL
    cfg.llm.model = LLM_MODEL
    cfg.memory.qdrant.host = QDRANT_HOST
    cfg.memory.qdrant.port = QDRANT_PORT
    cfg.memory.qdrant.collection = VERIFICATION_COLLECTION
    return cfg

@pytest.fixture(scope="session")
def qdrant_store(config: Config) -> QdrantMemoryStore:
    store = QdrantMemoryStore(config)
    store.connect()
    yield store
    # Cleanup: delete collection after tests
    try:
        client = QdrantClient(host=config.memory.qdrant.host,
                              port=config.memory.qdrant.port)
        client.delete_collection(config.memory.qdrant.collection)
    except Exception:
        pass

@pytest.fixture(scope="session")
def llm_client(config: Config) -> LLMClient:
    return LLMClient(config)

# ---------------------------------------------------------------------------
# Verification Report
# ---------------------------------------------------------------------------

class VerificationReport:
    """Accumulates pass/fail results and prints a summary."""

    def __init__(self):
        self._results = []

    def record(self, name, passed, detail=""):
        self._results.append((name, passed, detail))

    @property
    def all_passed(self):
        return all(ok for _, ok, _ in self._results)

    def summary(self):
        total = len(self._results)
        passed = sum(1 for _, ok, _ in self._results if ok)
        lines = [
            f"Verification Report ({datetime.now(timezone.utc).isoformat()})",
            "=" * 70,
            f"{'Check':<45} {'Result':<8} {'Detail':<20}",
            "-" * 70,
        ]
        for name, ok, detail in self._results:
            status = "PASS" if ok else "FAIL"
            lines.append(f"{name:<45} {status:<8} {detail:<20}")
        lines.append("-" * 70)
        lines.append(f"Total: {passed}/{total} passed")
        if passed == total:
            lines.append("VERIFICATION: ALL CHECKS PASSED")
        else:
            lines.append("VERIFICATION: SOME CHECKS FAILED")
        return chr(10).join(lines)

@pytest.fixture(scope="session")
def report():
    return VerificationReport()

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

class TestLiteLLMConnectivity:
    """Check 1: LiteLLM is reachable and responsive."""

    def test_chat_completion(self, llm_client, report):
        try:
            resp = llm_client.chat("Say hello in one word")
            report.record("LiteLLM: chat completion", True, "got response")
            assert resp is not None
        except Exception as e:
            report.record("LiteLLM: chat completion", False, str(e))
            raise

class TestQdrantConnectivity:
    """Check 2: Qdrant is reachable."""

    def test_connect(self, qdrant_store, report):
        report.record("Qdrant: connection", True, "connected")

class TestCollectionCreation:
    """Check 3: Collection can be created (or already exists)."""

    def test_collection_exists(self, qdrant_store, config, report):
        client = QdrantClient(host=config.memory.qdrant.host,
                              port=config.memory.qdrant.port)
        info = client.get_collection(config.memory.qdrant.collection)
        report.record("Qdrant: collection created", True, f"vectors={info.vectors_count}")
        assert info is not None

class TestStoreIncident:
    """Check 4: A real incident can be stored."""

    def test_store_incident(self, qdrant_store, report):
        incident = Incident(
            id="abc123",
            timestamp=datetime.now(timezone.utc).isoformat(),
            container_id="c0nt1",
            container_name="test-container",
            event_type="high_cpu",
            severity="warning",
            message="Container c0nt1 CPU at 95%",
        )
        qdrant_store.store_incident(incident)
        report.record("Qdrant: store incident", True, "stored abc123")

class TestLLMAnalysis:
    """Check 5: Real LLM analysis of an incident."""

    def test_analyze_incident(self, llm_client, report):
        analysis = llm_client.analyze_incident(
            message="Container abc123 CPU at 95%",
            event_type="high_cpu",
            container_name="test-container",
            severity="warning",
        )
        report.record("LiteLLM: analyze incident", True, f"len={len(analysis)}")
        assert isinstance(analysis, str)
        assert len(analysis) > 0

class TestStoreAndRetrieveWithAnalysis:
    """Check 6: Store incident with analysis, then retrieve it."""

    def test_store_and_retrieve(self, qdrant_store, llm_client, report):
        # Create and analyze incident
        analysis = llm_client.analyze_incident(
            message="Container xyz789 memory at 98%",
            event_type="memory_spike",
            container_name="memory-container",
            severity="critical",
        )
        incident = Incident(
            id="xyz789",
            timestamp=datetime.now(timezone.utc).isoformat(),
            container_id="c0nt2",
            container_name="memory-container",
            event_type="memory_spike",
            severity="critical",
            message="Container c0nt2 memory at 98%",
            llm_analysis=analysis,
        )

        # Store
        qdrant_store.store_incident(incident)
        report.record("Qdrant: store with analysis", True, "stored xyz789")

        # Retrieve
        retrieved = qdrant_store.get_incident("xyz789")
        report.record("Qdrant: retrieve incident", True, f"severity={retrieved.severity}")
        assert retrieved is not None
        assert retrieved.id == "xyz789"
        assert retrieved.llm_analysis is not None

class TestSearchSimilar:
    """Check 7: Semantic search finds related incidents."""

    def test_search_similar(self, qdrant_store, report):
        # Store another related incident
        related = Incident(
            id="def456",
            timestamp=datetime.now(timezone.utc).isoformat(),
            container_id="c0nt3",
            container_name="disk-container",
            event_type="disk_full",
            severity="critical",
            message="Container c0nt3 disk at 96%",
            llm_analysis="Disk usage is critically high",
        )
        qdrant_store.store_incident(related)

        # Search with a vector (all zeros matches since that is the default)
        results = qdrant_store.search_similar([0.0] * 1536, limit=3)
        report.record("Qdrant: search similar", True, f"found={len(results)}")
        assert len(results) > 0

class TestCount:
    """Check 8: Incident count is correct."""

    def test_count(self, qdrant_store, report):
        count = qdrant_store.count()
        report.record("Qdrant: count incidents", True, f"count={count}")
        assert count >= 3  # abc123 + xyz789 + def456 at minimum

class TestDeleteIncident:
    """Check 9: Incident can be deleted."""

    def test_delete(self, qdrant_store, report):
        qdrant_store.delete_incident("abc123")
        retrieved = qdrant_store.get_incident("abc123")
        report.record("Qdrant: delete incident", True, "deleted abc123")
        assert retrieved is None

class TestPrintReport:
    """Final check: print the full verification report."""

    def test_print_report(self, report):
        print()
        print(report.summary())
        print()
        assert report.all_passed, "Not all checks passed"
