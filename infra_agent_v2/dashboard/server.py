"""HTTP dashboard for Infra Agent v2.

Provides REST endpoints for monitoring agent status, container state,
incidents, recovery actions, and report generation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from infra_agent_v2.auth.middleware import AuthMiddleware
from infra_agent_v2.config import Config
from infra_agent_v2.utils.logging import setup_logging

logger = setup_logging(name="infra_agent.dashboard")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class DashboardServer:
    """FastAPI-based HTTP dashboard for the InfraAgent."""

    def __init__(self, agent):
        self.agent = agent
        self.config: Config = agent.config
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Infra Agent v2 Dashboard", version="0.1.0")

        # Apply authentication middleware
        app.add_middleware(
            AuthMiddleware,
            mode=self.config.dashboard.auth_mode,
            username=self.config.dashboard.auth_username,
            password=self.config.dashboard.auth_password,
            token=self.config.dashboard.auth_token,
        )

        @app.get("/api/status")
        def status():
            """Agent status and counters."""
            state = self.agent.state
            return {
                "running": state.running,
                "monitor_events": state.monitor_events,
                "health_events": state.health_events,
                "recovery_attempts": state.recovery_attempts,
                "correlation_groups": state.correlation_groups,
                "reports_generated": state.reports_generated,
                "last_report_time": state.last_report_time,
                "memory_connected": self.agent.memory is not None,
            }

        @app.get("/api/correlation")
        def correlation_groups():
            """Return active correlation groups."""
            groups = self.agent.correlator.get_active_groups()
            return [g.to_dict() for g in groups]

        @app.get("/api/correlation/{group_id}")
        def correlation_group(group_id: str):
            """Return a specific correlation group by ID."""
            group = self.agent.correlator.get_group(group_id)
            if group is None:
                raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
            return group.to_dict()

        @app.post("/api/correlation/flush")
        def flush_correlation():
            """Flush expired correlation groups."""
            expired = self.agent.correlator.flush_expired()
            return {"flushed": len(expired), "groups": [g.to_dict() for g in expired]}

        @app.post("/api/correlation/reset")
        def reset_correlation():
            """Reset all correlation state."""
            self.agent.correlator.reset()
            return {"reset": True}

        @app.get("/api/containers")
        def containers():
            """List all containers with their current state."""
            return self.agent.docker.list_containers()

        @app.get("/api/containers/{container_id}")
        def container_info(container_id: str):
            """Inspect a specific container."""
            stats = self.agent.docker.get_stats(container_id)
            if not stats:
                raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
            return {
                "container_id": container_id,
                "stats": stats,
                "restart_count": self.agent.recovery.get_restart_count(container_id),
                "in_cooldown": self.agent.recovery.is_in_cooldown(container_id),
            }

        @app.get("/api/incidents")
        def incidents(limit: int = 50):
            """Return recent incidents from Qdrant memory."""
            if self.agent.memory is None:
                return {"incidents": [], "error": "Memory store unavailable"}
            try:
                all_incidents = self.agent.memory.get_all()
                incidents = [inc.to_payload() for inc in all_incidents[-limit:]]
                return {"incidents": incidents, "total": len(all_incidents)}
            except Exception as exc:
                logger.error("Failed to fetch incidents: %s", exc)
                return {"incidents": [], "error": str(exc)}

        @app.get("/api/incidents/{incident_id}")
        def incident(incident_id: str):
            """Return a single incident from Qdrant memory."""
            if self.agent.memory is None:
                raise HTTPException(status_code=503, detail="Memory store unavailable")
            try:
                result = self.agent.memory.get_incident(incident_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))
            if result is None:
                raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
            return result.to_payload()

        @app.get("/api/incidents/similar/{query}")
        def similar_incidents(query: str, limit: int = 5):
            """Search for incidents similar to a query string."""
            return self.agent.analyzer.get_similar(query, limit=limit)

        @app.post("/api/recovery/{container_id}")
        def recover_container(container_id: str):
            """Trigger a recovery attempt for a container."""
            attempt = self.agent.recovery.recover(container_id)
            return {
                "container_id": container_id,
                "attempt_number": attempt.attempt_number,
                "success": attempt.success,
            }

        @app.post("/api/recovery/{container_id}/reset")
        def reset_recovery(container_id: str):
            """Reset recovery tracking for a container."""
            self.agent.recovery.reset(container_id)
            return {"container_id": container_id, "reset": True}

        @app.get("/api/report")
        def generate_report():
            """Generate a text report of recent incidents."""
            incidents: List[Dict] = []
            if self.agent.memory:
                try:
                    all_incidents = self.agent.memory.get_all()
                    incidents = [inc.to_payload() for inc in all_incidents[-50:]]
                except Exception:
                    pass
            return self.agent.reporter.generate_text(incidents, title="Dashboard Report")

        @app.get("/api/report/json")
        def generate_json_report():
            """Generate a JSON report of recent incidents."""
            incidents: List[Dict] = []
            if self.agent.memory:
                try:
                    all_incidents = self.agent.memory.get_all()
                    incidents = [inc.to_payload() for inc in all_incidents[-50:]]
                except Exception:
                    pass
            return self.agent.reporter.generate_json(incidents, title="Dashboard Report")

        @app.get("/api/health")
        def health():
            """Simple health check endpoint."""
            return {"status": "ok"}

        @app.get("/metrics")
        def metrics():
            """Prometheus metrics endpoint."""
            from prometheus_client import generate_latest
            return generate_latest()

        return app

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the dashboard server in a background thread."""
        import threading
        import uvicorn
        from uvicorn.config import Config as UvicornConfig

        uvicorn_config = UvicornConfig(
            app=self.app,
            host=host,
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(uvicorn_config)

        def _run():
            server.run()

        t = threading.Thread(target=_run, daemon=True, name="dashboard")
        t.start()
        logger.info("Dashboard server started at %s:%d", host, port)
