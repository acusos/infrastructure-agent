from pathlib import Path


SNAPSHOT_DIR = Path("snapshots")


def list_recent_snapshots(limit=10):

    if not SNAPSHOT_DIR.exists():
        return []

    snapshots = sorted(
        [
            f.name
            for f in SNAPSHOT_DIR.glob("*.json")
            if f.name != "latest.json"
        ],
        reverse=True,
    )

    return snapshots[:limit]


def snapshot_count():

    if not SNAPSHOT_DIR.exists():
        return 0

    return len(
        [
            f
            for f in SNAPSHOT_DIR.glob("*.json")
            if f.name != "latest.json"
        ]
    )


def oldest_snapshot():

    snapshots = sorted(
        [
            f.name
            for f in SNAPSHOT_DIR.glob("*.json")
            if f.name != "latest.json"
        ]
    )

    if not snapshots:
        return None

    return snapshots[0]


def newest_snapshot():

    snapshots = sorted(
        [
            f.name
            for f in SNAPSHOT_DIR.glob("*.json")
            if f.name != "latest.json"
        ]
    )

    if not snapshots:
        return None

    return snapshots[-1]


def get_snapshot_history():

    report = []

    report.append("SNAPSHOT HISTORY")
    report.append("")

    report.append(
        f"Total Snapshots: {snapshot_count()}"
    )

    report.append("")

    report.append(
        f"Newest: {newest_snapshot()}"
    )

    report.append(
        f"Oldest: {oldest_snapshot()}"
    )

    report.append("")
    report.append("Recent")
    report.append("------")

    for snapshot in list_recent_snapshots():
        report.append(snapshot)

    return "\n".join(report)


if __name__ == "__main__":

    print(
        get_snapshot_history()
    )
