import time

from src.tools.container_restart import restart_container

from src.tools.container_check import (
    check_vllm,
    check_litellm,
    check_qdrant,
    check_open_webui,
)


def recover_service(service):

    checks = {
        "vllm": check_vllm,
        "litellm": check_litellm,
        "qdrant": check_qdrant,
        "open-webui": check_open_webui,
    }

    if service not in checks:

        return (
            False,
            f"Unknown service: {service}"
        )

    restart_container(service)

    time.sleep(30)

    status = checks[service]()

    if "healthy" in status:

        return (
            True,
            f"{service} recovered successfully"
        )

    return (
        False,
        f"{service} still unhealthy after restart"
    )
