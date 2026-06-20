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

    findings = []

    if "Up" in status:
        findings.append("Status: Running")
    else:
        findings.append("Status: Not running")

    if "ERROR" in logs:
        findings.append("Errors detected in recent logs")

    if "ValueError" in logs:
        findings.append("Application exception detected")

    if "200 OK" in logs:
        findings.append("Successful API requests observed")

    if "healthy" in status.lower():
        findings.append("Container reports healthy state")

    if container_name == "vllm":

        if "200 OK" in logs:
            findings.append("Model serving operational")

        if "throughput" in logs.lower():
            findings.append("Inference activity detected")

    if container_name == "qdrant":

        if "listening on" in logs.lower():
            findings.append("Database ports active")

    if container_name == "open-webui":

        if "scheduler worker started" in logs.lower():
            findings.append("Background services active")

    if not findings:
        findings.append("No significant observations")

    return f"""
CONTAINER: {container_name}

STATUS

{status}

ASSESSMENT

""" + "\n".join(f"- {x}" for x in findings)
