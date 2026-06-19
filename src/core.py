from src.llm import ask_llm
from src.router import choose_tool

from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


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

    return None


def answer_question(question):

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
