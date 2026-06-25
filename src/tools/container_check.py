import requests

def check_llamacpp():

    try:

        r = requests.get(
            "http://127.0.0.1:8080/health",
            timeout=10,
        )

        if r.status_code == 200:
            return "llama-cpp healthy"

        return f"llama-cpp unhealthy (HTTP {r.status_code})"

    except Exception as e:

        return f"llama-cpp unhealthy ({e})"


def check_qdrant():

    try:

        r = requests.get(
            "http://127.0.0.1:6333",
            timeout=10,
        )

        if r.status_code == 200:
            return "qdrant healthy"

        return f"qdrant unhealthy (HTTP {r.status_code})"

    except Exception as e:

        return f"qdrant unhealthy ({e})"


def check_open_webui():

    try:

        r = requests.get(
            "http://127.0.0.1:3000",
            timeout=10,
        )

        if r.status_code < 500:
            return "open-webui healthy"

        return f"open-webui unhealthy (HTTP {r.status_code})"

    except Exception as e:

        return f"open-webui unhealthy ({e})"


def check_litellm():

    try:

        r = requests.get(
            "http://127.0.0.1:4000/health",
            timeout=10,
        )

        if r.status_code == 200:
            return "litellm healthy"

        return f"litellm unhealthy (HTTP {r.status_code})"

    except Exception as e:

        return f"litellm unhealthy ({e})"
