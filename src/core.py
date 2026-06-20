from src.llm import ask_llm
from src.router import choose_tool

from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services
from src.tools.health import get_health_status
from src.tools.logs import get_recent_errors

from src.tools.container_logs import get_container_logs
from src.tools.container_restart import restart_container
from src.tools.container_status import get_container_status


def run_tool(tool_name):

    if tool_name == "gpu":
        return get_gpu_status()

    if tool_name == "memory":
        return get_memory_status()

    if tool_name == "disk":
        return get_disk_status()

    if tool_name == "docker":
        return get_docker_status()

    if tool_name == "services":
        return get_failed_services()

    if tool_name == "health":
        return get_health_status()

    if tool_name == "logs":
        return get_recent_errors()

    return None


def answer_question(question):

    q = question.lower()

    #
    # Container Status
    #

    if "vllm" in q and (
        "status" in q
        or "healthy" in q
        or "health" in q
    ):
        return get_container_status("vllm")

    if "litellm" in q and (
        "status" in q
        or "healthy" in q
        or "health" in q
    ):
        return get_container_status("litellm")

    if "qdrant" in q and (
        "status" in q
        or "healthy" in q
        or "health" in q
    ):
        return get_container_status("qdrant")

    if "open-webui" in q and (
        "status" in q
        or "healthy" in q
        or "health" in q
    ):
        return get_container_status("open-webui")

    #
    # Container Restarts
    #

    if "restart vllm" in q:
        return restart_container("vllm")

    if "restart litellm" in q:
        return restart_container("litellm")

    if "restart qdrant" in q:
        return restart_container("qdrant")

    if "restart open-webui" in q:
        return restart_container("open-webui")

    #
    # Container Logs
    #

    if "logs for vllm" in q:
        return get_container_logs("vllm")

    if "logs for litellm" in q:
        return get_container_logs("litellm")

    if "logs for qdrant" in q:
        return get_container_logs("qdrant")

    if "logs for open-webui" in q:
        return get_container_logs("open-webui")

    #
    # Server Health
    #

    if (
        "health" in q
        or "healthy" in q
        or "system status" in q
        or "server status" in q
    ):

        report = get_health_status()

        return ask_llm(
            f"""
Using the health report below,
provide a concise summary.

{report}
"""
        )

    #
    # Errors
    #

    if (
        "error" in q
        or "errors" in q
        or "failed" in q
        or "failure" in q
        or "problem" in q
        or "problems" in q
        or "logs" in q
    ):

        errors = get_recent_errors()

        return ask_llm(
            f"""
Review these recent errors and
provide a concise summary.

{errors}
"""
        )

    tool = choose_tool(question)

    if tool == "none":
        return ask_llm(question)

    tool_output = run_tool(tool)

    return ask_llm(
        f"""
User question:
{question}

Tool output:
{tool_output}

Answer using ONLY the tool output.
"""
    )
