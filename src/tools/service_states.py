import json
from pathlib import Path


STATE_FILE = Path("monitor_state.json")


def load_states():

    if not STATE_FILE.exists():
        return {}

    return json.loads(
        STATE_FILE.read_text()
    )


def save_states(states):

    STATE_FILE.write_text(
        json.dumps(
            states,
            indent=2
        )
    )
