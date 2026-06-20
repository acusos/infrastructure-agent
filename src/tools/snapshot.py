import json
from pathlib import Path

from src.tools.system_check import run_system_check


SNAPSHOT_FILE = Path("snapshots/latest.json")


def save_snapshot():

    SNAPSHOT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "report": run_system_check()
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

    current = run_system_check()

    old_report = previous["report"]

    if old_report == current:
        return "No changes since last snapshot."

    return f"""
CHANGES DETECTED

PREVIOUS SNAPSHOT
-----------------
{old_report[:1000]}

CURRENT SNAPSHOT
----------------
{current[:1000]}
""".strip()
