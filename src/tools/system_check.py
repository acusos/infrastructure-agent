import os
import json
from pathlib import Path

from src.tools.container_check import (
    check_llamacpp,
    check_litellm,
    check_qdrant,
    check_open_webui,
)

from src.tools.health import get_health_status
from src.tools.logs import get_recent_errors
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status

STATE_FILE = Path("monitor_state.json")

def run_system_check():
    report = []

    report.append("AI SERVER REPORT")
    report.append("")

    report.append("SERVICES")
    report.append("--------")
    report.append(check_llamacpp())
    report.append(check_litellm())
    report.append(check_qdrant())
    report.append(check_open_webui())
    report.append("")

    report.append("INFRASTRUCTURE")
    report.append("--------------")
    report.append(get_health_status())
    report.append("")

    report.append("REMOTE SERVERS")
    report.append("--------------")
    states = load_state_file()
    for key, value in states.items():
        if key not in ["llama-cpp", "litellm", "qdrant", "open-webui", "cpu", "memory", "disk", "network"]:
            report.append(f"  {key}: {value}")
    report.append("")

    report.append("RESOURCES")
    report.append("---------")
    for key in ["cpu", "memory", "disk", "network"]:
        if key in states:
            report.append(f"  {key}: {states[key]}")
    report.append("")

    report.append("RECENT ERRORS")
    report.append("-------------")
    report.append(get_recent_errors())

    return "\n".join(report)

def load_state_file():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())
