import requests


def get_stack_status():

    status = {}

    services = {
        "vllm": "http://127.0.0.1:8000/v1/models",
        "litellm": "http://127.0.0.1:4000/model/info",
        "qdrant": "http://127.0.0.1:6333/",
        "open-webui": "http://127.0.0.1:3000"
    }

    for name, url in services.items():

        try:
            r = requests.get(url, timeout=5)
            status[name] = f"UP ({r.status_code})"

        except Exception:
            status[name] = "DOWN"

    return status
