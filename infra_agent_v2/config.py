"""Configuration management for Infra Agent v2."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResourceThresholds:
    cpu: float = 90.0
    memory: float = 90.0


@dataclass
class MonitorConfig:
    poll_interval: int = 5
    containers: List[str] = field(default_factory=list)
    resource_thresholds: ResourceThresholds = field(
        default_factory=ResourceThresholds
    )


@dataclass
class HealthEndpoint:
    name: str
    url: str
    interval: int = 10


@dataclass
class TcpCheck:
    host: str = "localhost"
    port: int = 5432
    interval: int = 15


@dataclass
class HealthConfig:
    endpoints: List[HealthEndpoint] = field(default_factory=list)
    tcp_checks: List[TcpCheck] = field(default_factory=list)


@dataclass
class RecoveryConfig:
    max_restarts: int = 3
    restart_cooldown: int = 60
    restart_timeout: int = 30


@dataclass
class LlmConfig:
    base_url: str = "http://192.168.20.116:4000"
    model: str = "gpt-4"
    temperature: float = 0.3


@dataclass
class QdrantConfig:
    host: str = "localhost"
    port: int = 6333
    collection: str = "infra_events"


@dataclass
class MemoryConfig:
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)


@dataclass
class DockerConfig:
    socket: str = "/var/run/docker.sock"
    network: str = "infra_network"


@dataclass
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    auth_mode: str = "basic"
    auth_username: str = "admin"
    auth_password: str = "admin"
    auth_token: str = ""


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class Config(BaseModel):
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> dict:
    """Load a YAML file and return its contents as a dict."""
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def _apply_env_overrides(config: Config) -> Config:
    """Override config values from environment variables (prefix INFRA_)."""
    # Monitor
    if "INFRA_MONITOR_POLL_INTERVAL" in os.environ:
        config.monitor.poll_interval = int(os.environ["INFRA_MONITOR_POLL_INTERVAL"])
    if "INFRA_MONITOR_CONTAINERS" in os.environ:
        config.monitor.containers = os.environ["INFRA_MONITOR_CONTAINERS"].split(",")

    # LLM
    if "INFRA_LLM_BASE_URL" in os.environ:
        config.llm.base_url = os.environ["INFRA_LLM_BASE_URL"]
    if "INFRA_LLM_MODEL" in os.environ:
        config.llm.model = os.environ["INFRA_LLM_MODEL"]

    # Docker
    if "INFRA_DOCKER_SOCKET" in os.environ:
        config.docker.socket = os.environ["INFRA_DOCKER_SOCKET"]

    # Recovery
    if "INFRA_RECOVERY_MAX_RESTARTS" in os.environ:
        config.recovery.max_restarts = int(os.environ["INFRA_RECOVERY_MAX_RESTARTS"])
    if "INFRA_RECOVERY_COOLDOWN" in os.environ:
        config.recovery.restart_cooldown = int(os.environ["INFRA_RECOVERY_COOLDOWN"])

    return config


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file with environment overrides.

    Args:
        config_path: Path to YAML config file. If None, tries
                     ``config.yaml`` in the same directory as this module.

    Returns:
        A ``Config`` instance with merged settings.
    """
    load_dotenv()

    # Start with defaults
    cfg = Config()

    # Layer YAML on top
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    cfg_dict = _load_yaml(config_path)

    if cfg_dict:
        _merge_yaml(cfg, cfg_dict)

    # Layer environment variables on top
    cfg = _apply_env_overrides(cfg)

    return cfg


def _merge_yaml(cfg: Config, data: dict) -> None:
    """Recursively merge a dict into a Config dataclass instance."""
    if "monitor" in data:
        m = data["monitor"]
        cfg.monitor.poll_interval = m.get("poll_interval", cfg.monitor.poll_interval)
        cfg.monitor.containers = m.get("containers", cfg.monitor.containers)
        if "resource_thresholds" in m:
            rt = m["resource_thresholds"]
            cfg.monitor.resource_thresholds.cpu = rt.get(
                "cpu", cfg.monitor.resource_thresholds.cpu
            )
            cfg.monitor.resource_thresholds.memory = rt.get(
                "memory", cfg.monitor.resource_thresholds.memory
            )

    if "health" in data:
        h = data["health"]
        for ep in h.get("endpoints", []):
            cfg.health.endpoints.append(HealthEndpoint(**ep))
        for tc in h.get("tcp_checks", []):
            cfg.health.tcp_checks.append(TcpCheck(**tc))

    if "recovery" in data:
        r = data["recovery"]
        cfg.recovery.max_restarts = r.get("max_restarts", cfg.recovery.max_restarts)
        cfg.recovery.restart_cooldown = r.get(
            "restart_cooldown", cfg.recovery.restart_cooldown
        )
        cfg.recovery.restart_timeout = r.get("restart_timeout", cfg.recovery.restart_timeout)

    if "llm" in data:
        l = data["llm"]
        cfg.llm.base_url = l.get("base_url", cfg.llm.base_url)
        cfg.llm.model = l.get("model", cfg.llm.model)
        cfg.llm.temperature = l.get("temperature", cfg.llm.temperature)

    if "memory" in data:
        mem = data["memory"]
        if "qdrant" in mem:
            q = mem["qdrant"]
            cfg.memory.qdrant.host = q.get("host", cfg.memory.qdrant.host)
            cfg.memory.qdrant.port = q.get("port", cfg.memory.qdrant.port)
            cfg.memory.qdrant.collection = q.get(
                "collection", cfg.memory.qdrant.collection
            )

    if "docker" in data:
        d = data["docker"]
        cfg.docker.socket = d.get("socket", cfg.docker.socket)
        cfg.docker.network = d.get("network", cfg.docker.network)

    if "dashboard" in data:
        db = data["dashboard"]
        cfg.dashboard.host = db.get("host", cfg.dashboard.host)
        cfg.dashboard.port = db.get("port", cfg.dashboard.port)
