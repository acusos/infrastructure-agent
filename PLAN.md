# Infra Agent v2 - Implementation Plan

## 1. Project Structure

```
infra_agent_v2/
├── AGENTS.md
├── ARCHITECTURE.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── requirements.txt
├── README.md
├── infra_agent_v2/
│   ├── __init__.py
│   ├── config.py
│   ├── monitor/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── health/
│   │   ├── __init__.py
│   │   └── checker.py
│   ├── report/
│   │   ├── __init__.py
│   │   └── generator.py
│   ├── recovery/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── analyzer.py
│   ├── memory/
│   │   ├── __init__.py
│   │   └── qdrant_store.py
│   ├── actions/
│   │   ├── __init__.py
│   │   └── docker_actions.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── logging.py
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

## 2. Dependency List

### Core
| Package | Version | Purpose |
|---------|---------|---------|
| `pyyaml` | 6.0.2 | Configuration parsing |
| `python-dotenv` | 1.0.1 | Environment variables |
| `pydantic` | 2.10.6 | Data validation |
| `python-dateutil` | 2.9.0 | Date parsing and formatting |

### Monitoring
| Package | Version | Purpose |
|---------|---------|---------|
| `docker` | 7.1.0 | Docker SDK for container management |

### LLM
| Package | Version | Purpose |
|---------|---------|---------|
| `litellm` | 1.57.1 | LLM proxy client |
| `openai` | 1.60.0 | OpenAI-compatible client |

### Memory
| Package | Version | Purpose |
|---------|---------|---------|
| `qdrant-client` | 1.12.1 | Vector database client |

### Testing
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | 8.3.4 | Test framework |
| `pytest-asyncio` | 0.25.3 | Async test support |
| `pytest-cov` | 6.0.0 | Coverage reporting |
| `responses` | 0.25.6 | HTTP mocking |

## 3. Implementation Phases

### Phase 1: Foundation
1. Create project structure
2. Implement configuration management (`config.py`)
3. Set up logging infrastructure (`utils/logging.py`)

### Phase 2: Docker Integration
4. Implement Docker actions module (`actions/docker_actions.py`)
5. Implement monitor engine (`monitor/engine.py`)
6. Implement health checker (`health/checker.py`)

### Phase 3: Intelligence
7. Implement LLM analyzer (`llm/analyzer.py`)
8. Implement Qdrant memory store (`memory/qdrant_store.py`)

### Phase 4: Recovery & Reporting
9. Implement recovery engine (`recovery/engine.py`)
10. Implement report generator (`report/generator.py`)

### Phase 5: Integration
11. Implement main entry point (`main.py`)
12. Wire all components together

### Phase 6: Testing
13. Write unit tests for each module
14. Write integration tests
15. Set up Docker Compose for local development

## 4. Configuration Schema

```yaml
# config.yaml
monitor:
  poll_interval: 5           # seconds
  containers: []             # empty = all containers
  resource_thresholds:
    cpu: 90                  # percent
    memory: 90               # percent

health:
  endpoints:                 # list of HTTP health checks
    - name: app
      url: http://localhost:8000/health
      interval: 10
  tcp_checks:                # list of TCP health checks
    - host: localhost
      port: 5432
      interval: 15

recovery:
  max_restarts: 3            # max restarts before alerting
  restart_cooldown: 60       # seconds between restart attempts
  restart_timeout: 30        # seconds to wait for container to start

llm:
  base_url: http://192.168.20.116:4000
  model: gpt-4
  temperature: 0.3

memory:
  qdrant:
    host: localhost
    port: 6333
    collection: infra_events

docker:
  socket: /var/run/docker.sock
  network: infra_network

dashboard:
  host: 0.0.0.0
  port: 8000
```

## 5. Event Model

Every event is stored in Qdrant with:
- `timestamp`: ISO 8601
- `type`: `container_stop`, `container_start`, `health_failure`, `recovery_attempt`, etc.
- `container_id`: Docker container ID
- `severity`: `info`, `warning`, `critical`
- `message`: Description
- `llm_analysis`: (optional) LLM-generated summary
- `vector`: Embedding of message for semantic search

## 6. Key Design Decisions

1. **Polling over Events**: Monitor engine polls Docker API on a configurable interval rather than relying on Docker events API, for reliability.
2. **Cooldown on Restart**: Recovery engine enforces a cooldown period to prevent restart loops.
3. **Max Restarts**: After `max_restarts` attempts, the agent alerts rather than retrying.
4. **LLM as Classifier**: LiteLLM is used to classify incident severity and summarize root causes, not to control infrastructure.
5. **Qdrant for Retention**: All events are persisted with vector embeddings for semantic search of past incidents.