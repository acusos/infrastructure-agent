from src.tools.container_status import get_container_status
from src.tools.container_logs import get_container_logs


ALLOWED_CONTAINERS = {
    "vllm",
    "litellm",
    "qdrant",
    "open-webui",
}


def diagnose_container(container_name):

    if container_name not in ALLOWED_CONTAINERS:
        return f"Container not allowed: {container_name}"

    status = get_container_status(container_name)
    logs = get_container_logs(container_name)

    return f"""
CONTAINER STATUS

{status}

RECENT LOGS

{logs}
""".strip()
