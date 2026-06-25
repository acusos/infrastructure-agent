# Infra Agent v2

Container monitoring, incident analysis, and automated recovery agent.

Monitors Docker containers, analyzes incidents via LLM, attempts automated recovery, and generates structured reports.

## Features

- **Container Monitoring** — Polls Docker for state changes and resource threshold breaches
- **Health Checking** — HTTP and TCP health checks against configured endpoints
- **LLM Analysis** — Classifies incident severity and generates root-cause hypotheses via LiteLLM
- **Persistent Memory** — Stores incidents with embeddings in Qdrant for semantic search
- **Auto-Recovery** — Restarts crashed containers with configurable cooldown and max-restart limits
- **Reporting** — Structured incident reports in plain text and JSON

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start the agent
python -m infra_agent_v2.main
# or: infra-agent
```

## Docker Compose

```bash
docker-compose up --build
```

Starts Qdrant (port 6333) and the agent (port 8000) together.

## Configuration

See `config.yaml` for the default configuration, or override via environment variables (prefix `INFRA_`). Copy `.env.example` to `.env` to customize.

## Architecture

```
MonitorEngine ──┐
                ├──→ IncidentAnalyzer ──→ QdrantMemoryStore
HealthChecker  ──┘
                └──→ RecoveryEngine (on critical events)
                └──→ ReportGenerator (periodic)
```

## License

MIT
