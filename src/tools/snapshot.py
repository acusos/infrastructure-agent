import json
from pathlib import Path
from datetime import datetime

from src.tools.system_metrics import get_system_metrics


SNAPSHOT_FILE = Path("snapshots/latest.json")


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
        json.dumps(data, indent=2)
    )

    return f"Snapshot saved to {SNAPSHOT_FILE}"


def load_snapshot():

    if not SNAPSHOT_FILE.exists():
        return None

    return json.loads(
        SNAPSHOT_FILE.read_text()
    )


def compare_snapshot():

    previous = load_snapshot()

    if not previous:
        return "No snapshot exists."

    current = get_system_metrics()
    old = previous["metrics"]

    changes = []

    #
    # GPU
    #

    if (
        old["gpu"]["temperature_c"]
        != current["gpu"]["temperature_c"]
    ):
        changes.append(
            f"GPU temperature: "
            f'{old["gpu"]["temperature_c"]}C -> '
            f'{current["gpu"]["temperature_c"]}C'
        )

    if (
        old["gpu"]["memory_used_mib"]
        != current["gpu"]["memory_used_mib"]
    ):
        changes.append(
            f"GPU memory used: "
            f'{old["gpu"]["memory_used_mib"]} MiB -> '
            f'{current["gpu"]["memory_used_mib"]} MiB'
        )

    #
    # Memory
    #

    if (
        old["memory"]["used_gb"]
        != current["memory"]["used_gb"]
    ):
        changes.append(
            f"RAM used: "
            f'{old["memory"]["used_gb"]} GB -> '
            f'{current["memory"]["used_gb"]} GB'
        )

    #
    # Docker
    #

    if (
        old["docker"]["running_containers"]
        != current["docker"]["running_containers"]
    ):
        changes.append(
            f"Running containers: "
            f'{old["docker"]["running_containers"]} -> '
            f'{current["docker"]["running_containers"]}'
        )

    #
    # Services
    #

    for service in (
        "vllm",
        "litellm",
        "qdrant",
        "open_webui",
    ):

        if old[service] != current[service]:

            changes.append(
                f"{service}: "
                f'{old[service]} -> {current[service]}'
            )

    if not changes:

        return "No significant changes since last snapshot."

    report = []

    report.append("SNAPSHOT COMPARISON")
    report.append("")
    report.append(
        f"Snapshot Time: {previous['timestamp']}"
    )
    report.append("")
    report.append("CHANGES")
    report.append("-------")

    for change in changes:
        report.append(change)

    return "\n".join(report)
