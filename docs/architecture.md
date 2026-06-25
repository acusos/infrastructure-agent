# Infra Agent v2 — Architecture

## Overview

Infra Agent v2 is an autonomous infrastructure monitoring and remediation system
built on a **monitor → correlate → analyze → act** pipeline. It watches
Docker containers, runs health checks, analyzes incidents with an LLM,
correlates related events, triggers recovery, and reports findings — all
through a single orchestrator process.

## Components

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Monitor     │───▶│ Correlator   │───▶│  Analyzer    │
│  Engine      │    │              │    │  (LLM)       │
└──────────────┘    └──────────────┘    └──────────────┘
       │                      │                    │
       ▼                      ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Docker      │    │  Memory      │    │  Recovery    │
│  Actions     │    │  (Qdrant)    │    │  Engine      │
└──────────────┘    └──────────────┘    └──────────────┘
       │                      │                    │
       ▼                      ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Dashboard   │    │  Reporter    │    │  Alerter     │
│  (FastAPI)   │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### MonitorEngine
Polls Docker containers for resource usage and state changes.
Configurable thresholds for CPU and memory.

### HealthChecker
Runs HTTP and TCP health checks on configurable endpoints.

### IncidentCorrelator
Groups related incidents by container and time window to detect
cascading failures.

### IncidentAnalyzer
Sends incidents to an LLM for root-cause analysis and suggested
remediation.

### RecoveryEngine
Automatically restarts failing containers, respects max restarts
and cooldown periods.

### QdrantMemoryStore
Persistent event store using Qdrant vector database. Supports
semantic search for similar past incidents.

### DashboardServer
FastAPI-based HTTP dashboard with REST endpoints for status,
containers, incidents, and recovery actions.

### ReportGenerator
Periodically generates human-readable incident reports.

### StateManager
Persists agent runtime state to disk for recovery across restarts.

### ShutdownHandler
Handles SIGINT/SIGTERM gracefully, saves state before exit.

### ConfigWatcher
Monitors the config file for changes and triggers hot-reload.

### MetricsCollector
Prometheus metrics for monitoring the agent itself.

## Data Flow

1. **Monitor** detects container event → emits `MonitorEvent`
2. **Correlator** groups related events → may create `CorrelationGroup`
3. **Analyzer** sends to LLM → produces `LLMAnalysis`
4. If critical → **RecoveryEngine** attempts restart
5. If recovery fails → **Alerter** dispatches alert
6. All data stored in **Qdrant** for persistence and search
7. **Dashboard** exposes everything via REST API
