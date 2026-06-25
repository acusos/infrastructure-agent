# Infra Agent v2 — Deployment Guide

## Prerequisites

- Python 3.11–3.13
- Docker Engine (with `/var/run/docker.sock` accessible)
- Qdrant instance (optional, for persistent memory)
- LLM endpoint (optional, for incident analysis)

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/acusos/infrastructure-agent.git
cd infrastructure-agent

# 2. Configure (optional)
cp config.example.yaml config.yaml  # if provided

# 3. Run
python -m infra_agent_v2.main
```

## Configuration

### YAML Config (`config.yaml`)

```yaml
monitor:
  poll_interval: 5
  containers: []
  resource_thresholds:
    cpu: 90.0
    memory: 90.0

health:
  endpoints:
    - name: api
      url: http://localhost:8000/api/health
      interval: 10
  tcp_checks:
    - host: localhost
      port: 5432
      interval: 15

recovery:
  max_restarts: 3
  restart_cooldown: 60
  restart_timeout: 30

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
  auth_mode: basic
  auth_username: admin
  auth_password: secret
  auth_token: ""
```

### Environment Variables

All config values can be overridden with `INFRA_` prefixed variables:

| Variable | Description |
|----------|-------------|
| `INFRA_MONITOR_POLL_INTERVAL` | Monitor poll interval (seconds) |
| `INFRA_MONITOR_CONTAINERS` | Comma-separated container list |
| `INFRA_LLM_BASE_URL` | LLM base URL |
| `INFRA_LLM_MODEL` | LLM model name |
| `INFRA_DASHBOARD_USERNAME` | Dashboard username |
| `INFRA_DASHBOARD_PASSWORD` | Dashboard password |
| `INFRA_DASHBOARD_TOKEN` | Dashboard bearer token |

## Docker Deployment

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["python", "-m", "infra_agent_v2.main"]
```

## CI/CD

GitHub Actions workflows are provided:

- `ci.yml` — Lint, test, and quality checks
- `docker.yml` — Build Docker image on push to `main`
- `release.yml` — Publish to registry on tag

## Monitoring

- **Dashboard**: `http://<host>:8000/api/status`
- **Metrics**: `http://<host>:8000/metrics` (Prometheus format)
- **Health**: `http://<host>:8000/api/health`
