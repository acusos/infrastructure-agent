"""Tests for the LiteLLM client."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.llm.client import LLMClient

LLM_ENDPOINT = "http://192.168.20.116:4000"


class TestLLMClient:

    def test_init_uses_correct_base_url(self, config):
        client = LLMClient(config)
        assert client._base_url == LLM_ENDPOINT

    def test_init_uses_correct_model(self, config):
        client = LLMClient(config)
        assert client._model == "gpt-4"

    def test_init_uses_correct_temperature(self, config):
        client = LLMClient(config)
        assert client._temperature == 0.3

    @patch("infra_agent_v2.llm.client.litellm")
    def test_chat_returns_response(self, mock_litellm, config):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Test response"
        mock_litellm.completion.return_value = mock_resp

        client = LLMClient(config)
        result = client.chat("Hello")
        assert result == "Test response"

    @patch("infra_agent_v2.llm.client.litellm")
    def test_chat_sends_system_and_user_messages(self, mock_litellm, config):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "OK"
        mock_litellm.completion.return_value = mock_resp

        client = LLMClient(config)
        client.chat("Hello", system="Be concise")
        call_args = mock_litellm.completion.call_args
        msgs = call_args[1]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Be concise"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "Hello"

    @patch("infra_agent_v2.llm.client.litellm")
    def test_chat_uses_correct_model(self, mock_litellm, config):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "OK"
        mock_litellm.completion.return_value = mock_resp

        client = LLMClient(config)
        client.chat("Hello")
        call_args = mock_litellm.completion.call_args
        assert call_args[1]["model"] == "openai/gpt-4"
        assert call_args[1]["base_url"] == LLM_ENDPOINT

    @patch("infra_agent_v2.llm.client.litellm")
    def test_analyze_incident(self, mock_litellm, config):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Analysis result"
        mock_litellm.completion.return_value = mock_resp

        client = LLMClient(config)
        result = client.analyze_incident(
            message="web crashed",
            event_type="crash",
            container_name="web",
            severity="critical",
        )
        assert result == "Analysis result"

    @patch("infra_agent_v2.llm.client.litellm")
    def test_generate_embedding(self, mock_litellm, config):
        mock_resp = MagicMock()
        mock_resp.data[0].embedding = [0.1, 0.2, 0.3]
        mock_litellm.embedding.return_value = mock_resp

        client = LLMClient(config)
        vec = client.generate_embedding("hello")
        assert vec == [0.1, 0.2, 0.3]

    @patch("infra_agent_v2.llm.client.litellm")
    def test_generate_embedding_fallback(self, mock_litellm, config):
        mock_litellm.embedding.side_effect = Exception("no embedding model")

        client = LLMClient(config)
        vec = client.generate_embedding("hello")
        assert vec == [0.0] * 1536

    @patch("infra_agent_v2.llm.client.litellm")
    def test_generate_embeddings_batch(self, mock_litellm, config):
        mock_item0 = MagicMock()
        mock_item0.embedding = [0.1]
        mock_item1 = MagicMock()
        mock_item1.embedding = [0.2]
        mock_resp = MagicMock()
        mock_resp.data = [mock_item0, mock_item1]
        mock_litellm.embedding.return_value = mock_resp

        client = LLMClient(config)
        vecs = client.generate_embeddings_batch(["hello", "world"])
        assert len(vecs) == 2
        assert vecs[0] == [0.1]

    @patch("infra_agent_v2.llm.client.litellm")
    def test_batch_embedding_fallback(self, mock_litellm, config):
        mock_litellm.embedding.side_effect = Exception("no model")

        client = LLMClient(config)
        vecs = client.generate_embeddings_batch(["a", "b"])
        assert len(vecs) == 2
        assert vecs[0] == [0.0] * 1536
