"""LLM-powered incident analyzer for Infra Agent v2.

Receives container events, sends them through the LLM for classification,
correlates with past incidents via Qdrant, and persists analysis results.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.llm.client import LLMClient
from infra_agent_v2.memory.qdrant_store import Incident, QdrantMemoryStore
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.analyzer")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SEVERITY_CLASSIFY_PROMPT = (
    "You are an infrastructure incident analyst.\n"
    "Classify the following container event and assign a severity.\n\n"
    "Event type: {event_type}\n"
    "Container: {container_name}\n"
    "Message: {message}\n\n"
    "Respond with a single word: info, warning, critical"
)

ROOT_CAUSE_PROMPT = (
    "You are an infrastructure incident analyst.\n"
    "Analyze the following incident and provide a concise root-cause hypothesis\n"
    "and recommended remediation steps.\n\n"
    "Event type: {event_type}\n"
    "Container: {container_name}\n"
    "Message: {message}\n"
    "Severity: {severity}\n\n"
    "Respond with:\n"
    "- Root cause hypothesis:\n"
    "- Recommended actions:\n"
)

# ---------------------------------------------------------------------------
# Analysis Result
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """Result of analyzing an incident through the LLM and memory pipeline."""
    incident: Incident
    severity: str
    similar_incidents: List[Incident] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class IncidentAnalyzer:
    """LLM-powered incident analysis and correlation.

    Pipeline:
      1. Receive event → create Incident
      2. LLM severity classification
      3. LLM root-cause analysis
      4. Store to Qdrant with embedding
      5. Search for similar past incidents
    """

    def __init__(self, config: Config, llm_client: Optional[LLMClient] = None,
                 memory_store: Optional[QdrantMemoryStore] = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)
        self.store = memory_store or QdrantMemoryStore(config)

    # -- Public API --

    def analyze(self, event_type: str, container_name: str,
                message: str, container_id: str = "") -> AnalysisResult:
        """Run the full analysis pipeline on a single event.

        1. Create an Incident object.
        2. Classify severity via LLM.
        3. Generate root-cause analysis via LLM.
        4. Embed and store the incident in Qdrant.
        5. Search for similar past incidents.
        """
        incident = self._create_incident(event_type, container_name, message, container_id)

        severity = self._classify_severity(event_type, container_name, message)
        incident.severity = severity

        analysis = self._analyze_root_cause(event_type, container_name, message, severity)
        incident.llm_analysis = analysis

        embedding = self._embed_incident(incident)
        self.store.store_incident(incident, vector=embedding)

        similar = self._find_similar(embedding, limit=3)

        return AnalysisResult(incident=incident, severity=severity,
                              similar_incidents=similar)

    def classify(self, event_type: str, container_name: str,
                 message: str) -> str:
        """Quick LLM severity classification without full pipeline."""
        return self._classify_severity(event_type, container_name, message)

    def analyze_root_cause(self, event_type: str, container_name: str,
                           message: str, severity: str = "unknown") -> str:
        """Generate a root-cause analysis without persisting."""
        return self._analyze_root_cause(event_type, container_name, message, severity)

    def get_similar(self, message: str, limit: int = 5) -> List[Incident]:
        """Search Qdrant for incidents similar to the given message."""
        embedding = self._embed_text(message)
        return self._find_similar(embedding, limit=limit)

    # -- Internal --

    @staticmethod
    def _create_incident(event_type: str, container_name: str,
                         message: str, container_id: str) -> Incident:
        return Incident(
            id=uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            container_id=container_id or hashlib.sha256(
                container_name.encode()
            ).hexdigest()[:12],
            container_name=container_name,
            event_type=event_type,
            severity="unknown",
            message=message,
        )

    def _classify_severity(self, event_type: str, container_name: str,
                           message: str) -> str:
        """Classify event severity via LLM. Falls back to heuristic."""
        try:
            prompt = SEVERITY_CLASSIFY_PROMPT.format(
                event_type=event_type,
                container_name=container_name,
                message=message,
            )
            response = self.llm.chat(prompt, system="You are a strict incident severity classifier. Respond with exactly one word: info, warning, or critical.")
            severity = response.strip().lower()
            if severity in ("info", "warning", "critical"):
                return severity
            return "warning"  # fallback if LLM returns something unexpected
        except Exception:
            logger.warning("LLM severity classification failed; using heuristic")
            return self._heuristic_severity(event_type, message)

    @staticmethod
    def _heuristic_severity(event_type: str, message: str) -> str:
        """Fallback severity classification without LLM."""
        msg_lower = message.lower()
        if "crash" in event_type or "oom" in msg_lower or "panic" in msg_lower:
            return "critical"
        if "restart" in event_type or "unhealthy" in msg_lower:
            return "warning"
        return "info"

    def _analyze_root_cause(self, event_type: str, container_name: str,
                            message: str, severity: str) -> str:
        """Generate root-cause analysis via LLM. Falls back to template."""
        try:
            prompt = ROOT_CAUSE_PROMPT.format(
                event_type=event_type,
                container_name=container_name,
                message=message,
                severity=severity,
            )
            return self.llm.chat(prompt)
        except Exception:
            logger.warning("LLM root-cause analysis failed; returning template")
            return (
                f"[Auto] Root cause hypothesis: {event_type} on {container_name}.\n"
                f"Recommended actions: Inspect logs, check resource usage, "
                f"verify network connectivity."
            )

    def _embed_incident(self, incident: Incident) -> List[float]:
        """Generate embedding for an incident."""
        text = f"{incident.event_type} {incident.container_name} {incident.message}"
        return self._embed_text(text)

    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding for text. Falls back to zero vector."""
        try:
            return self.llm.generate_embedding(text)
        except Exception:
            logger.warning("Embedding generation failed; using zero vector")
            return [0.0] * 1536

    def _find_similar(self, vector: List[float], limit: int = 3) -> List[Incident]:
        """Search Qdrant for similar incidents."""
        try:
            return self.store.search_similar(vector, limit=limit)
        except Exception:
            logger.warning("Similar incident search failed")
            return []
