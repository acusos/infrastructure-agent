from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


def get_health_status():

    gpu = get_gpu_status()
    memory = get_memory_status()
    disk = get_disk_status()
    docker = get_docker_status()
    services = get_failed_services()

    warnings = []

    if gpu["memory_free_mib"] < 2048:
        warnings.append(
            f"Low GPU free memory ({gpu['memory_free_mib']} MiB)"
        )

    if gpu["temperature_c"] > 80:
        warnings.append(
            f"High GPU temperature ({gpu['temperature_c']}C)"
        )

    docker_count = max(
        len(docker.strip().splitlines()) - 1,
        0
    )

    report = f"""
AI SERVER HEALTH

GPU
  Model: {gpu['name']}
  VRAM Free: {gpu['memory_free_mib']} MiB
  VRAM Used: {gpu['memory_used_mib']} MiB
  Temperature: {gpu['temperature_c']}C

MEMORY
{memory}

DOCKER
  Running Containers: {docker_count}

SERVICES
{services}

STORAGE
  Review detailed disk output below.

{disk}
"""

    if warnings:

        report += "\nWARNINGS\n"

        for warning in warnings:
            report += f"  - {warning}\n"

    else:

        report += "\nWARNINGS\n  None\n"

    return report
