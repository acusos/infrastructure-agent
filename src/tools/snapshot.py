import json
from pathlib import Path
from datetime import datetime

from src.tools.system_metrics import (
    get_system_metrics,
)


SNAPSHOT_FILE = Path(
    "snapshots/latest.json"
)


def save_snapshot():

    SNAPSHOT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "timestamp": datetime.now().isoformat(),
        "metrics": get_system_metrics(),
    }

    SNAPSHOT_FILE.write_text(
        json.dumps(
            data,
            indent=2,
        )
    )

    return (
        f"Snapshot saved to "
        f"{SNAPSHOT_FILE}"
    )


def load_snapshot():

    if not SNAPSHOT_FILE.exists():
        return None

    return json.loads(
        SNAPSHOT_FILE.read_text()
    )


def compare_snapshot():

    snapshot = load_snapshot()

    if not snapshot:
        return "No snapshot exists."

    old = snapshot["metrics"]
    current = get_system_metrics()

    snapshot_time = datetime.fromisoformat(
        snapshot["timestamp"]
    )

    age = datetime.now() - snapshot_time

    changes = []

    #
    # GPU Temperature
    #

    old_temp = old["gpu"]["temperature_c"]
    new_temp = current["gpu"]["temperature_c"]

    temp_delta = new_temp - old_temp

    if abs(temp_delta) >= 3:

        changes.append(
            f"Temperature: "
            f"{old_temp}C -> {new_temp}C "
            f"({temp_delta:+}C)"
        )

    #
    # GPU Memory
    #

    old_vram = old["gpu"]["memory_used_mib"]
    new_vram = current["gpu"]["memory_used_mib"]

    vram_delta = (
        new_vram - old_vram
    )

    if abs(vram_delta) >= 500:

        changes.append(
            f"VRAM Used: "
            f"{old_vram} MiB -> "
            f"{new_vram} MiB "
            f"({vram_delta:+} MiB)"
        )

    #
    # RAM
    #

    old_ram = old["memory"]["used_gb"]
    new_ram = current["memory"]["used_gb"]

    ram_delta = round(
        new_ram - old_ram,
        1
    )

    if abs(ram_delta) >= 0.5:

        changes.append(
            f"RAM Used: "
            f"{old_ram} GB -> "
            f"{new_ram} GB "
            f"({ram_delta:+} GB)"
        )

    #
    # Containers
    #

    old_containers = (
        old["docker"][
            "running_containers"
        ]
    )

    new_containers = (
        current["docker"][
            "running_containers"
        ]
    )

    if old_containers != new_containers:

        changes.append(
            f"Containers: "
            f"{old_containers} -> "
            f"{new_containers}"
        )

    #
    # Services
    #

    service_changes = []

    for service in (
        "vllm",
        "litellm",
        "qdrant",
        "open_webui",
    ):

        if old[service] != current[service]:

            service_changes.append(
                f"{service}: "
                f"{old[service]} -> "
                f"{current[service]}"
            )

    report = []

    report.append(
        "SNAPSHOT COMPARISON"
    )
    report.append("")

    report.append(
        f"Snapshot Age: "
        f"{age.seconds // 3600}h "
        f"{(age.seconds % 3600) // 60}m"
    )

    report.append("")

    report.append("SERVICES")
    report.append("--------")

    if service_changes:

        report.extend(
            service_changes
        )

    else:

        report.append(
            "No service changes"
        )

    report.append("")

    report.append("RESOURCE CHANGES")
    report.append("----------------")

    if changes:

        report.extend(changes)

    else:

        report.append(
            "No significant resource changes"
        )

    report.append("")
    report.append("OVERALL")
    report.append("-------")

    if (
        not service_changes
        and not changes
    ):

        report.append(
            "System stable since snapshot."
        )

    elif service_changes:

        report.append(
            "Service state changed."
        )

    else:

        report.append(
            "Resource usage changed."
        )

    return "\n".join(report)
