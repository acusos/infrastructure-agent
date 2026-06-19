from src.llm import ask_llm
from src.router import choose_tool

from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


def run_tool(tool_name: str):

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


print("Infrastructure Agent")
print("Type 'exit' to quit")
print()

while True:

    question = input("> ").strip()

    if question.lower() in ["exit", "quit"]:
        break

    try:

        tool = choose_tool(question)

        print(f"[router] selected tool: {tool}")
        print()

        if tool == "none":

            response = ask_llm(question)

            print(response)
            print()

            continue

        tool_output = run_tool(tool)

        prompt = f"""
You are a Linux infrastructure assistant.

User question:

{question}

Selected tool:

{tool}

Tool output:

{tool_output}

Answer the user's question using ONLY the tool output.

Do not invent information.
Do not estimate values.
Be concise.
"""

        response = ask_llm(prompt)

        print(response)
        print()

    except Exception as e:

        print()
        print(f"ERROR: {e}")
        print()
