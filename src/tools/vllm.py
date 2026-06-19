import requests

def get_vllm_status():

    try:
        r = requests.get(
            "http://127.0.0.1:8000/v1/models",
            timeout=5
        )

        return r.json()

    except Exception as e:
        return {"error": str(e)}
