import subprocess


ALLOWED_CONTAINERS = {
    "vllm",
    "litellm",
    "qdrant",
    "open-webui",
}


def restart_container(container_name):

    if container_name not in ALLOWED_CONTAINERS:

        return f"Container not allowed: {container_name}"

    try:

        output = subprocess.check_output(
            [
                "docker",
                "restart",
                container_name,
            ],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )

        return output.strip()

    except Exception as e:

        return str(e)
