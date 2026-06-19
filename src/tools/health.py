from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


def get_health_status():

    return {
        "gpu": get_gpu_status(),
        "memory": get_memory_status(),
        "disk": get_disk_status(),
        "docker": get_docker_status(),
        "services": get_failed_services()
    }
