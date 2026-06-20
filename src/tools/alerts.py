from src.tools.container_check import (
    check_vllm,
    check_litellm,
    check_qdrant,
    check_open_webui,
)

from src.tools.system_metrics import get_system_metrics


def check_alerts():

    alerts = []

    #
    # Services
    #

    if check_vllm() != "vllm healthy":
        alerts.append("vllm unhealthy")

    if check_litellm() != "litellm healthy":
        alerts.append("litellm unhealthy")

    if check_qdrant() != "qdrant healthy":
        alerts.append("qdrant unhealthy")

    if check_open_webui() != "open-webui healthy":
        alerts.append("open-webui unhealthy")

    #
    # GPU
    #

    metrics = get_system_metrics()

    gpu_temp = metrics["gpu"]["temperature_c"]

    if gpu_temp >= 80:
        alerts.append(
            f"GPU temperature high ({gpu_temp}C)"
        )

    #
    # RAM
    #

    ram_percent = metrics["memory"]["usage_percent"]

    if ram_percent >= 90:
        alerts.append(
            f"RAM usage high ({ram_percent}%)"
        )

    if not alerts:
        return "No alerts"

    return "\n".join(alerts)
