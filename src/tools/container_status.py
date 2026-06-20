import subprocess


ALLOWED_CONTAINERS = {
    "vllm",
    "litellm",
    "qdrant",
    "open-webui",
}


def get_container_status(container_name):

    if container_name not in ALLOWED_CONTAINERS:
        return f"Container not allowed: {container_name}"

    try:

        output = subprocess.check_output(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            ],
            text=True,
            timeout=10,
        )

        return output

    except Exception as e:

        return str(e)
