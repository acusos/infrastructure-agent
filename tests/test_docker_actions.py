"""Tests for actions/docker_actions.py."""

from unittest.mock import MagicMock, patch

import pytest

from infra_agent_v2.config import Config
from infra_agent_v2.actions.docker_actions import DockerActions, ActionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Return a mock Docker client."""
    return MagicMock()

@pytest.fixture
def mock_container():
    """Return a mock container object."""
    c = MagicMock()
    c.id = "container-123"
    c.short_id = "c123"
    c.name = "test-container"
    c.status = "running"
    return c

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

class TestDockerActionsBasic:
    """Basic initialization and client wiring."""

    def test_init_with_client(self, config, mock_client):
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.client is mock_client

    def test_start_success(self, config, mock_client, mock_container):
        actions = DockerActions(config, docker_client=mock_client)
        mock_client.containers.get.return_value = mock_container
        result = actions.start("c123")
        assert result.success is True
        assert result.action == "start"
        mock_client.containers.get.return_value.start.assert_called_once()

    def test_stop_success(self, config, mock_client, mock_container):
        actions = DockerActions(config, docker_client=mock_client)
        mock_client.containers.get.return_value = mock_container
        result = actions.stop("c123")
        assert result.success is True
        assert result.action == "stop"

    def test_restart_success(self, config, mock_client, mock_container):
        actions = DockerActions(config, docker_client=mock_client)
        mock_client.containers.get.return_value = mock_container
        result = actions.restart("c123")
        assert result.success is True
        assert result.action == "restart"

    def test_kill_success(self, config, mock_client, mock_container):
        actions = DockerActions(config, docker_client=mock_client)
        mock_client.containers.get.return_value = mock_container
        result = actions.kill("c123")
        assert result.success is True
        assert result.action == "kill"

    def test_remove_success(self, config, mock_client, mock_container):
        actions = DockerActions(config, docker_client=mock_client)
        mock_client.containers.get.return_value = mock_container
        result = actions.remove("c123")
        assert result.success is True
        assert result.action == "remove"

# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------

class TestDockerActionsFailures:
    """Actions handle errors gracefully."""

    def test_start_failure(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("not found")
        actions = DockerActions(config, docker_client=mock_client)
        result = actions.start("c123")
        assert result.success is False
        assert "not found" in result.details

    def test_stop_failure(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("connection error")
        actions = DockerActions(config, docker_client=mock_client)
        result = actions.stop("c123")
        assert result.success is False

    def test_restart_failure(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("timeout")
        actions = DockerActions(config, docker_client=mock_client)
        result = actions.restart("c123")
        assert result.success is False
        assert result.details == "timeout"

# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

class TestDockerActionsInspection:
    """Logs, inspect, stats, list."""

    def test_logs(self, config, mock_client, mock_container):
        mock_client.containers.get.return_value = mock_container
        mock_container.logs.return_value = b"line1\nline2"
        actions = DockerActions(config, docker_client=mock_client)
        logs = actions.logs("c123")
        assert "line1" in logs
        assert "line2" in logs

    def test_logs_empty_on_error(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("error")
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.logs("c123") == ""

    def test_inspect(self, config, mock_client, mock_container):
        mock_client.containers.get.return_value = mock_container
        mock_container.attrs = {"State": {"Status": "running"}}
        actions = DockerActions(config, docker_client=mock_client)
        info = actions.inspect("c123")
        assert info["State"]["Status"] == "running"

    def test_inspect_empty_on_error(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("error")
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.inspect("c123") == {}

    def test_get_stats(self, config, mock_client, mock_container):
        mock_client.containers.get.return_value = mock_container
        mock_container.stats.return_value = {"cpu_stats": {}}
        actions = DockerActions(config, docker_client=mock_client)
        stats = actions.get_stats("c123")
        assert "cpu_stats" in stats

    def test_get_stats_empty_on_error(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("error")
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.get_stats("c123") == {}

    def test_list_containers(self, config, mock_client, mock_container):
        mock_client.containers.list.return_value = [mock_container]
        actions = DockerActions(config, docker_client=mock_client)
        result = actions.list_containers()
        assert len(result) == 1
        assert result[0]["name"] == "test-container"

    def test_list_containers_empty_on_error(self, config, mock_client):
        mock_client.containers.list.side_effect = Exception("error")
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.list_containers() == []

    def test_is_running_true(self, config, mock_client, mock_container):
        mock_client.containers.get.return_value = mock_container
        mock_container.status = "running"
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.is_running("c123") is True

    def test_is_running_false(self, config, mock_client, mock_container):
        mock_client.containers.get.return_value = mock_container
        mock_container.status = "exited"
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.is_running("c123") is False

    def test_is_running_exception(self, config, mock_client):
        mock_client.containers.get.side_effect = Exception("not found")
        actions = DockerActions(config, docker_client=mock_client)
        assert actions.is_running("c123") is False
