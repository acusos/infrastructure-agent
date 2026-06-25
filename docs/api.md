# Infra Agent v2 — API Reference

## Dashboard REST API

Base URL: `http://<host>:<port>/` (default `0.0.0.0:8000`)

### Authentication

The dashboard supports two authentication modes, configurable in
`config.yaml`:

| Mode    | Config key          | Description                          |
|---------|---------------------|--------------------------------------|
| `basic` | `auth_username`, `auth_password` | HTTP Basic Auth |
| `bearer` | `auth_token`       | Bearer token in Authorization header |

Public endpoints (`/api/health`, `/metrics`) do not require auth.

---

### Endpoints

#### `GET /api/health`
Health check.

#### `GET /metrics`
Prometheus metrics exposition format.

#### `GET /api/status`
Agent status and counters.

#### `GET /api/containers`
List all containers.

#### `GET /api/containers/<id>`
Inspect a specific container.

#### `GET /api/incidents?limit=50`
Recent incidents.

#### `GET /api/incidents/<id>`
Single incident.

#### `GET /api/incidents/similar/<query>`
Semantic search for similar incidents.

#### `POST /api/recovery/<id>`
Trigger recovery for a container.

#### `POST /api/recovery/<id>/reset`
Reset recovery tracking.

#### `GET /api/correlation`
Active correlation groups.

#### `POST /api/correlation/flush`
Flush expired groups.

#### `POST /api/correlation/reset`
Reset all correlation state.

#### `GET /api/report`
Generate text report.

#### `GET /api/report/json`
Generate JSON report.

---

### Prometheus Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `infra_monitor_events_total` | Counter | `event_type`, `severity` |
| `infra_health_events_total` | Counter | `check_name`, `status` |
| `infra_health_check_result` | Gauge | `check_name` |
| `infra_recovery_attempts_total` | Counter | `container_name`, `success` |
| `infra_recovery_alerts_total` | Counter | `container_name` |
| `infra_alerts_sent_total` | Counter | — |
| `infra_config_reloads_total` | Counter | — |
| `infra_reports_generated_total` | Counter | — |
| `infra_correlation_groups` | Gauge | — |
| `infra_uptime_seconds` | Gauge | — |
| `infra_incident_latency_seconds` | Histogram | — |
