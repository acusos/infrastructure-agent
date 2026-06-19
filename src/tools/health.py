from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


def get_mount_free_space(disk_output, mountpoint):

    for line in disk_output.splitlines():

        if line.strip().endswith(f" {mountpoint}"):

            parts = line.split()

            if len(parts) >= 6:
                return parts[3]

    return "unknown"


def get_health_status():

    gpu = get_gpu_status()
    memory = get_memory_status()
    disk = get_disk_status()
    docker = get_docker_status()
    services = get_failed_services()

    warnings = []

    docker_count = max(
        len(docker.strip().splitlines()) - 1,
        0
    )

    if gpu["temperature_c"] > 80:
        warnings.append(
            f"High GPU temperature ({gpu['temperature_c']}C)"
        )

    if docker_count == 0:
        warnings.append(
            "No Docker containers running"
        )

    if "0 loaded units listed" not in services:
        warnings.append(
            "Failed services detected"
        )

    report = f"""
AI SERVER HEALTH

STATUS
  Healthy

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
  No failed services detected

STORAGE

  /models: {get_mount_free_space(disk, "/models")} free
  /var/lib/docker: {get_mount_free_space(disk, "/var/lib/docker")} free
  /data: {get_mount_free_space(disk, "/data")} free
  /home: {get_mount_free_space(disk, "/home")} free
  /: {get_mount_free_space(disk, "/")} free
"""

    if warnings:

        report += "\nWARNINGS\n"

        for warning in warnings:
            report += f"  - {warning}\n"

    else:

        report += "\nWARNINGS\n  None\n"

    return report
