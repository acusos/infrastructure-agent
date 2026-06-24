"""Tests for configuration management."""

import os
import tempfile
from textwrap import dedent

import pytest
import yaml

from infra_agent_v2.config import (
    Config,
    HealthEndpoint,
    QdrantConfig,
    TcpCheck,
    load_config,
)


class TestDefaultConfig:
    """Verify default configuration values."""

    def test_defaults(self, config):
        assert config.monitor.poll_interval == 5
        assert config.monitor.containers == []
        assert config.monitor.resource_thresholds.cpu == 90.0
        assert config.monitor.resource_thresholds.memory == 90.0

    def test_health_defaults(self, config):
        assert config.health.endpoints == []
        assert config.health.tcp_checks == []

    def test_recovery_defaults(self, config):
        assert config.recovery.max_restarts == 3
        assert config.recovery.restart_cooldown == 60
        assert config.recovery.restart_timeout == 30

    def test_llm_defaults(self, config):
        assert config.llm.base_url == "http://192.168.20.116:4000"
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.3

    def test_qdrant_defaults(self, config):
        assert config.memory.qdrant.host == "localhost"
        assert config.memory.qdrant.port == 6333
        assert config.memory.qdrant.collection == "infra_events"

    def test_docker_defaults(self, config):
        assert config.docker.socket == "/var/run/docker.sock"
        assert config.docker.network == "infra_network"


class TestLoadConfigFromFile:
    """Test YAML-based configuration loading."""

    def _write_config(self, data: dict) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(data, tmp)
        tmp.close()
        return tmp.name

    def test_load_yaml_monitor(self):
        path = self._write_config({
            "monitor": {
                "poll_interval": 10,
                "containers": ["web", "db"],
                "resource_thresholds": {"cpu": 80, "memory": 85},
            }
        })
        cfg = load_config(path)
        assert cfg.monitor.poll_interval == 10
        assert cfg.monitor.containers == ["web", "db"]
        assert cfg.monitor.resource_thresholds.cpu == 80
        assert cfg.monitor.resource_thresholds.memory == 85

    def test_load_yaml_llm(self):
        path = self._write_config({
            "llm": {"base_url": "http://custom:8000", "model": "llama3"}
        })
        cfg = load_config(path)
        assert cfg.llm.base_url == "http://custom:8000"
        assert cfg.llm.model == "llama3"

    def test_load_yaml_recovery(self):
        path = self._write_config({
            "recovery": {
                "max_restarts": 5,
                "restart_cooldown": 120,
                "restart_timeout": 60,
            }
        })
        cfg = load_config(path)
        assert cfg.recovery.max_restarts == 5
        assert cfg.recovery.restart_cooldown == 120
        assert cfg.recovery.restart_timeout == 60

    def test_load_yaml_health_endpoints(self):
        path = self._write_config({
            "health": {
                "endpoints": [
                    {"name": "app", "url": "http://localhost:8000/health", "interval": 10},
                ]
            }
        })
        cfg = load_config(path)
        assert len(cfg.health.endpoints) == 1
        assert cfg.health.endpoints[0].name == "app"

    def test_load_yaml_health_tcp(self):
        path = self._write_config({
            "health": {
                "tcp_checks": [
                    {"host": "localhost", "port": 5432, "interval": 15},
                ]
            }
        })
        cfg = load_config(path)
        assert len(cfg.health.tcp_checks) == 1
        assert isinstance(cfg.health.tcp_checks[0], TcpCheck)

    def test_load_yaml_qdrant(self):
        path = self._write_config({
            "memory": {
                "qdrant": {"host": "qdrant-host", "port": 7777, "collection": "my_events"}
            }
        })
        cfg = load_config(path)
        assert cfg.memory.qdrant.host == "qdrant-host"
        assert cfg.memory.qdrant.port == 7777
        assert cfg.memory.qdrant.collection == "my_events"

    def test_load_yaml_docker(self):
        path = self._write_config({
            "docker": {"socket": "/custom/sock", "network": "my_net"}
        })
        cfg = load_config(path)
        assert cfg.docker.socket == "/custom/sock"
        assert cfg.docker.network == "my_net"

    def test_missing_file_uses_defaults(self):
        cfg = load_config("/nonexistent/config.yaml")
        assert cfg.monitor.poll_interval == 5

    def test_empty_yaml_file(self):
        path = self._write_config({})
        cfg = load_config(path)
        assert cfg.monitor.poll_interval == 5

    def test_partial_yaml(self):
        path = self._write_config({"monitor": {"poll_interval": 20}})
        cfg = load_config(path)
        assert cfg.monitor.poll_interval == 20
        # Other fields stay default
        assert cfg.docker.socket == "/var/run/docker.sock"

    def test_merge_yaml_all_fields(self):
        data = {
            "monitor": {
                "poll_interval": 10,
                "containers": ["web", "db"],
                "resource_thresholds": {"cpu": 80, "memory": 85},
            },
            "health": {
                "endpoints": [
                    {"name": "app", "url": "http://localhost:8000/health", "interval": 10},
                ],
                "tcp_checks": [
                    {"host": "localhost", "port": 5432, "interval": 15},
                ],
            },
            "recovery": {"max_restarts": 5, "restart_cooldown": 120, "restart_timeout": 60},
            "llm": {"base_url": "http://custom:8000", "model": "llama3", "temperature": 0.5},
            "memory": {
                "qdrant": {"host": "qdrant-host", "port": 7777, "collection": "my_events"},
            },
            "docker": {"socket": "/custom/sock", "network": "my_net"},
            "dashboard": {"host": "127.0.0.1", "port": 9000},
        }
        path = self._write_config(data)
        cfg = load_config(path)
        # Verify every section was merged
        assert cfg.monitor.poll_interval == 10
        assert cfg.monitor.containers == ["web", "db"]
        assert cfg.monitor.resource_thresholds.cpu == 80
        assert cfg.monitor.resource_thresholds.memory == 85
        assert len(cfg.health.endpoints) == 1
        assert len(cfg.health.tcp_checks) == 1
        assert cfg.recovery.max_restarts == 5
        assert cfg.recovery.restart_cooldown == 120
        assert cfg.recovery.restart_timeout == 60
        assert cfg.llm.base_url == "http://custom:8000"
        assert cfg.llm.model == "llama3"
        assert cfg.llm.temperature == 0.5
        assert cfg.memory.qdrant.host == "qdrant-host"
        assert cfg.memory.qdrant.port == 7777
        assert cfg.memory.qdrant.collection == "my_events"
        assert cfg.docker.socket == "/custom/sock"
        assert cfg.docker.network == "my_net"
        assert cfg.dashboard.host == "127.0.0.1"
        assert cfg.dashboard.port == 9000


class TestEnvOverrides:
    """Test environment variable overrides."""

    def test_env_monitor_poll(self, monkeypatch):
        monkeypatch.setenv("INFRA_MONITOR_POLL_INTERVAL", "20")
        cfg = load_config()
        assert cfg.monitor.poll_interval == 20

    def test_env_monitor_containers(self, monkeypatch):
        monkeypatch.setenv("INFRA_MONITOR_CONTAINERS", "web,api,db")
        cfg = load_config()
        assert cfg.monitor.containers == ["web", "api", "db"]

    def test_env_llm_base_url(self, monkeypatch):
        monkeypatch.setenv("INFRA_LLM_BASE_URL", "http://custom:9000")
        cfg = load_config()
        assert cfg.llm.base_url == "http://custom:9000"

    def test_env_llm_model(self, monkeypatch):
        monkeypatch.setenv("INFRA_LLM_MODEL", "llama3")
        cfg = load_config()
        assert cfg.llm.model == "llama3"

    def test_env_docker_socket(self, monkeypatch):
        monkeypatch.setenv("INFRA_DOCKER_SOCKET", "/custom/sock")
        cfg = load_config()
        assert cfg.docker.socket == "/custom/sock"

    def test_env_recovery_max_restarts(self, monkeypatch):
        monkeypatch.setenv("INFRA_RECOVERY_MAX_RESTARTS", "10")
        cfg = load_config()
        assert cfg.recovery.max_restarts == 10

    def test_env_recovery_cooldown(self, monkeypatch):
        monkeypatch.setenv("INFRA_RECOVERY_COOLDOWN", "180")
        cfg = load_config()
        assert cfg.recovery.restart_cooldown == 180

    def test_env_overrides_yaml(self, monkeypatch):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            yaml.dump({"monitor": {"poll_interval": 5}}, tmp)
        monkeypatch.setenv("INFRA_MONITOR_POLL_INTERVAL", "30")
        cfg = load_config(tmp.name)
        assert cfg.monitor.poll_interval == 30
