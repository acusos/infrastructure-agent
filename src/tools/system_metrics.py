from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.docker import get_docker_status

from src.tools.container_check import (
    check_vllm,
    check_litellm,
    check_qdrant,
    check_open_webui,
)


def get_system_metrics():

    return {
        "gpu": get_gpu_status(),
        "memory": get_memory_status(),
        "docker": get_docker_status(),
        "vllm": check_vllm(),
        "litellm": check_litellm(),
        "qdrant": check_qdrant(),
        "open_webui": check_open_webui(),
    }
