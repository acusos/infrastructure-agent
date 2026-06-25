# Infra Agent v2 — Repository Skill

## Status: Phases 1-9 complete, 256/256 tests passing

## Quick Start
```bash
pip install -e ".[dev]"
pytest
docker-compose up --build
```

## Architecture
The agent monitors Docker containers, analyzes incidents via LLM, attempts automated recovery, and generates reports.

```
MonitorEngine ──┐
                ├──→ IncidentCorrelator ──→ IncidentAnalyzer ──→ QdrantMemoryStore
HealthChecker  ──┘
                └──→ RecoveryEngine (on critical events)
                └──→ ReportGenerator (periodic)
                └──→ AlertEngine (notifications)
                └──→ DashboardServer (HTTP API)
                └──→ StateManager (persistence)
```

- **Monitor** (`monitor/engine.py`) — Polls Docker for state changes and resource threshold breaches
- **Health Checker** (`health/checker.py`) — HTTP + TCP health checks against configured endpoints
- **Correlator** (`correlation/correlator.py`) — Groups events within time windows into single correlation groups
- **LLM Analyzer** (`llm/analyzer.py` + `llm/client.py`) — Classifies severity, generates root-cause hypotheses
- **Qdrant Memory** (`memory/qdrant_store.py`) — Persistent incident storage with semantic search
- **Recovery Engine** (`recovery/engine.py`) — Auto-restarts containers with cooldown and max-restart limits
- **Report Generator** (`report/generator.py`) — Structured incident reports (text + JSON)
- **Alert Engine** (`alerting/engine.py`) — Pluggable notification system (logger + webhook handlers)
- **Orchestrator** (`main.py`) — Wires all subsystems together with event routing
- **Dashboard Server** (`dashboard/server.py`) — HTTP REST API for monitoring and control
- **State Manager** (`state/persistence.py`) — Runtime state persistence

## Build Commands
- Install: `pip install -e ".[dev]"`
- Test: `pytest tests/ -v`
- Run: `python -m infra_agent_v2.main` or `infra-agent` (via pyproject scripts)
- Docker: `docker-compose up --build`

## Key Patterns
- All subsystems accept optional mockable dependencies for testability
- Event handlers registered via `register_handler()` callbacks
- LLM calls always have heuristic fallbacks
- Qdrant is optional — agent continues without it
- Recovery enforces `restart_cooldown` and `max_restarts` before alerting
- `poll_once()` on monitor/health allows non-blocking one-shot runs
- Correlation groups events within `poll_interval * 30` seconds; same-container events stay in the same group
- Alert handlers are pluggable; `INFRA_ALERT_WEBHOOK_URL` configures webhook handler
