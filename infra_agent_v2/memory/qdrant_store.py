"""Qdrant-backed persistent memory for Infra Agent v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.memory")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Incident data model
# ---------------------------------------------------------------------------

@dataclass
class Incident:
    """Represents an incident stored in Qdrant."""
    id: str
    timestamp: str
    container_id: str
    container_name: str
    event_type: str
    severity: str
    message: str
    llm_analysis: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "llm_analysis": self.llm_analysis,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> Incident:
        return cls(
            id=payload["id"],
            timestamp=payload["timestamp"],
            container_id=payload["container_id"],
            container_name=payload["container_name"],
            event_type=payload["event_type"],
            severity=payload["severity"],
            message=payload["message"],
            llm_analysis=payload.get("llm_analysis"),
        )


# ---------------------------------------------------------------------------
# Memory Store
# ---------------------------------------------------------------------------

class QdrantMemoryStore:
    """Stores and retrieves incidents using Qdrant."""

    DEFAULT_DIM = 1536

    def __init__(self, config: Config, client: Optional[QdrantClient] = None):
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed")

        self.config = config.memory.qdrant
        self.client = client or self._build_client()
        self._initialized = False

    @staticmethod
    def _build_client() -> QdrantClient:
        return QdrantClient(host="localhost", port=6333)

    def connect(self) -> None:
        """Ensure the client is connected and the collection exists."""
        try:
            self.client.get_collections()
        except Exception:
            logger.error("Failed to connect to Qdrant at %s:%d",
                         self.config.host, self.config.port)
            raise
        self._ensure_collection()
        self._initialized = True

    def _ensure_collection(self) -> None:
        """Create the Qdrant collection if it does not already exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.config.collection in collections:
            return
        self.client.create_collection(
            collection_name=self.config.collection,
            vectors_config=models.VectorParams(
                size=self.DEFAULT_DIM,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection '%s'", self.config.collection)

    def store_incident(self, incident: Incident, vector: Optional[List[float]] = None) -> None:
        if not self._initialized:
            self.connect()

        vec = vector if vector is not None else [0.0] * self.DEFAULT_DIM
        payload = incident.to_payload()

        self.client.upsert(
            collection_name=self.config.collection,
            points=[
                models.PointStruct(
                    id=incident.id,
                    vector=vec,
                    payload=payload,
                ),
            ],
        )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        if not self._initialized:
            self.connect()

        results = self.client.retrieve(
            collection_name=self.config.collection,
            ids=[incident_id],
        )
        if not results:
            return None
        return Incident.from_payload(results[0].payload)

    def search_similar(self, query_vector: List[float], limit: int = 5) -> List[Incident]:
        if not self._initialized:
            self.connect()

        results = self.client.query_points(
            collection_name=self.config.collection,
            query=query_vector,
            limit=limit,
        )
        return [Incident.from_payload(p.payload) for p in results.points]

    def get_all(self) -> List[Incident]:
        if not self._initialized:
            self.connect()

        results = self.client.scroll(
            collection_name=self.config.collection,
            limit=10000,
        )
        return [Incident.from_payload(p.payload) for p in results[0]]

    def count(self) -> int:
        if not self._initialized:
            self.connect()

        info = self.client.get_collection(self.config.collection)
        return int(info.vectors_count) if hasattr(info, 'vectors_count') else 0

    def delete_incident(self, incident_id: str) -> bool:
        if not self._initialized:
            self.connect()

        try:
            self.client.delete(
                collection_name=self.config.collection,
                points_selector=models.PointIdsList(points=[incident_id]),
            )
            return True
        except Exception:
            return False
