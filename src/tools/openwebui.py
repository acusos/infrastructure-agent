import requests

def get_openwebui_status():

    try:
        r = requests.get(
            "http://127.0.0.1:3000/health",
            timeout=5
        )

        return r.status_code

    except Exception as e:
        return str(e)
