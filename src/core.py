from src.llm import ask_llm
from src.router import choose_tool

from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services
from src.tools.health import get_health_status
from src.tools.logs import get_recent_errors


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

    if (
        "health" in q
        or "healthy" in q
        or "system status" in q
        or "server status" in q
    ):

        tool_output = get_health_status()

        prompt = f"""
You are a Linux infrastructure assistant.

Using the health report below, provide a concise summary.

Health Report:

{tool_output}
"""

        return ask_llm(prompt)

    if (
        "error" in q
        or "errors" in q
        or "failed" in q
        or "failure" in q
        or "problem" in q
        or "problems" in q
        or "logs" in q
    ):

        tool_output = get_recent_errors()

        prompt = f"""
You are a Linux infrastructure assistant.

Review these recent errors and provide a concise summary.

Errors:

{tool_output}
"""

        return ask_llm(prompt)

    tool = choose_tool(question)

    if tool == "none":

        return ask_llm(question)

    tool_output = run_tool(tool)

    prompt = f"""
You are a Linux infrastructure assistant.

User question:
{question}

Selected tool:
{tool}

Tool output:
{tool_output}

Answer using ONLY the tool output.

Be concise.
"""

    return ask_llm(prompt)
