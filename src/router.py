from src.llm import ask_llm


def choose_tool(question: str) -> str:

    prompt = f"""
You are a tool router.

Available tools:

gpu       - GPU status and VRAM usage
memory    - RAM usage
disk      - filesystem usage
docker    - running docker containers
services  - failed systemd services

If no tool applies, return:

none

User question:

{question}

Return ONLY one word:

gpu
memory
disk
docker
services
none
"""

    result = ask_llm(prompt)

    if not result:
        return "none"

    result = result.strip().lower()

    if "gpu" in result:
        return "gpu"

    if "memory" in result:
        return "memory"

    if "disk" in result:
        return "disk"

    if "docker" in result:
        return "docker"

    if "services" in result:
        return "services"

    return "none"
