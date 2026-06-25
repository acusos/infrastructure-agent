from src.tools.container_check import (
    check_llamacpp,
    check_litellm,
    check_qdrant,
    check_open_webui,
)

from src.tools.health import get_health_status
from src.tools.logs import get_recent_errors


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

    report.append("RECENT ERRORS")
    report.append("-------------")
    report.append(get_recent_errors())

    return "\n".join(report)
