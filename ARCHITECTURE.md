# Infra Agent v2 - Architecture Document

## 1. Overview

Infra Agent v2 is an infrastructure monitoring and remediation system that watches Docker containers, checks service health, generates reports, and automatically restarts failed containers. Findings are stored persistently in Qdrant, and the agent uses LiteLLM (via proxy at 192.168.20.116:4000) to analyze incidents and produce natural-language summaries.

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     Infra Agent v2                           │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  Monitor      │──►│  Health      │──►│  Recovery       │  │
│  │  Engine       │   │  Checker     │   │  (restart)      │  │
│  └──────┬───────┘   └──────┬───────┘   └─────────────────┘  │
│         │                   │                                │
│    ┌────▼─────┐        ┌────▼──────────┐                    │
│    │ Docker   │        │ LLM Analyzer   │                    │
│    │ API      │        │ (LiteLLM)      │                    │
│    └──────────┘        └────┬──────────┘                    │
│                             │                                │
│    ┌────────────────────────▼─────────────────────────────┐  │
│    │                  Report Generator                     │  │
│    └────────────────────────┬─────────────────────────────┘  │
│                             │                                │
│    ┌────────────────────────▼─────────────────────────────┐  │
│    │                   Qdrant Store                         │  │
│    └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                 Action Engine                          │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## 3. Core Components

### 3.1 Monitor Engine
Continuously polls Docker daemon for container state changes. Detects:
- Container starts, stops, crashes, and exits with non-zero codes
- Resource usage thresholds (CPU, memory, disk I/O)
- Long-running containers without health check updates

### 3.2 Health Checker
Performs liveness and readiness checks against known services:
- HTTP/HTTPS endpoint probes (configurable)
- TCP port connectivity
- Docker health check status
- Container log analysis for error patterns

### 3.3 Recovery Module
Automated remediation for failed containers:
- Restart policy enforcement
- Rolling restart with health verification
- Rollback on repeated failures
- Notification on recovery actions

### 3.4 LLM Analyzer
Uses LiteLLM via proxy at 192.168.20.116:4000 to:
- Classify incident severity (info / warning / critical)
- Summarize failure root causes from logs
- Suggest remediation steps
- Generate human-readable report sections

### 3.5 Report Generator
Compiles findings into structured reports:
- Markdown-formatted summaries
- JSON data exports
- Per-container and per-service breakdowns
- Historical trend data

### 3.6 Qdrant Memory Store
Persistent vector-based storage for:
- Incident embeddings (semantic search of past events)
- Container state snapshots
- Configuration snapshots
- LLM analysis results

### 3.7 Action Engine
Orchestrates remediation actions:
- Container restart via Docker API
- Service dependency ordering
- Cooldown period to prevent restart loops
- Approval gates for destructive actions

### 3.8 Configuration Management
YAML-based configuration with environment variable overrides:
- Monitoring targets (container names, services)
- Health check endpoints and thresholds
- LLM proxy settings
- Qdrant connection settings
- Docker credentials and network settings

## 4. Directory Structure

```
infra_agent_v2/
├── AGENTS.md                     # Persistent memory for agent workflows
├── ARCHITECTURE.md               # This file
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── requirements.txt
├── README.md
├── infra_agent_v2/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── monitor/
│   │   ├── __init__.py
│   │   └── engine.py             # Container state monitoring
│   ├── health/
│   │   ├── __init__.py
│   │   └── checker.py            # Service health probes
│   ├── report/
│   │   ├── __init__.py
│   │   └── generator.py          # Report generation
│   ├── recovery/
│   │   ├── __init__.py
│   │   └── engine.py             # Auto-restart logic
│   ├── llm/
│   │   ├── __init__.py
│   │   └── analyzer.py           # LiteLLM integration
│   ├── memory/
│   │   ├── __init__.py
│   │   └── qdrant_store.py       # Qdrant-backed storage
│   ├── actions/
│   │   ├── __init__.py
│   │   └── docker_actions.py     # Docker operations
│   └── utils/
│       ├── __init__.py
│       └── logging.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_monitor.py
│   ├── test_health.py
│   ├── test_report.py
│   ├── test_recovery.py
│   ├── test_llm.py
│   ├── test_memory.py
│   └── test_config.py
└── data/
```

## 5. Data Flow

```
1. Monitor Engine polls Docker API
      │
      ▼
2. State change detected → Health Checker validates
      │
      ▼
3. If unhealthy → LLM Analyzer classifies incident
      │
      ▼
4. Recovery Engine decides action (restart / alert / ignore)
      │
      ▼
5. Action Engine executes via Docker API
      │
      ▼
6. Report Generator compiles findings
      │
      ▼
7. Qdrant Store persists all events and analysis
```

## 6. Security Considerations

- Docker socket access is required; access controls should be scoped to read + restart only
- LLM proxy credentials stored in environment variables, never in code
- Recovery actions require cooldown periods to prevent restart storms
- Action engine logs all state changes for audit