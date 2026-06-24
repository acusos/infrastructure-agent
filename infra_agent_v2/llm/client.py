"""LiteLLM client for Infra Agent v2.

Wraps LiteLLM to provide LLM calls, incident analysis, and embeddings
via the local endpoint at http://192.168.20.116:4000.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.llm")

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

INCIDENT_ANALYSIS_PROMPT = (
    "You are an infrastructure incident analyst. "
    "Analyze the following incident and provide a concise root-cause hypothesis "
    "and recommended remediation steps.\n\n"
    "Incident: {message}\n"
    "Event type: {event_type}\n"
    "Container: {container_name}\n"
    "Severity: {severity}\n\n"
    "Respond with:\n"
    "- Root cause hypothesis:\n"
    "- Recommended actions:\n"
)

# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Client for interacting with the LLM via LiteLLM."""

    def __init__(self, config: Config):
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is not installed")

        self.config = config.llm
        self._base_url = self.config.base_url.rstrip("/")
        self._model = self.config.model
        self._temperature = self.config.temperature
        self._api_key = "local"  # Required for local OpenAI-compatible endpoints

        # Configure LiteLLM to use the local OpenAI-compatible endpoint
        litellm.set_verbose = True

    def chat(self, prompt: str, system: str = "You are a helpful infrastructure assistant.") -> str:
        """Send a chat completion and return the assistant message text.

        Args:
            prompt: The user message to send.
            system: Optional system instruction (default: generic).

        Returns:
            The assistant's response text.

        Raises:
            litellm.LitellmException: On any LLM-level error.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        response = litellm.completion(
            model="openai/" + self._model,
            messages=messages,
            base_url=self._base_url,
            temperature=self._temperature,
            api_key=self._api_key,
        )

        return response.choices[0].message.content

    def analyze_incident(
        self,
        message: str,
        event_type: str,
        container_name: str,
        severity: str,
    ) -> str:
        """Analyze an incident using the LLM.

        Args:
            message: Incident description.
            event_type: Type of event (crash, state_change, threshold).
            container_name: Name of the affected container.
            severity: Incident severity level.

        Returns:
            LLM-generated analysis text.
        """
        prompt = INCIDENT_ANALYSIS_PROMPT.format(
            message=message,
            event_type=event_type,
            container_name=container_name,
            severity=severity,
        )
        return self.chat(prompt)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for the given text.

        Uses the configured model's embedding capability. Falls back to
        a zero-vector if the model does not support embeddings.

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding.
        """
        try:
            response = litellm.embedding(
                model="openai/text-embedding-3-small",
                input=text,
                base_url=self._base_url,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("Embedding generation failed: %s; returning zero vector", exc)
            return [0.0] * 1536

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors, one per input text.
        """
        try:
            response = litellm.embedding(
                model="openai/text-embedding-3-small",
                input=texts,
                base_url=self._base_url,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.warning("Batch embedding failed: %s; returning zero vectors", exc)
            return [[0.0] * 1536 for _ in texts]
