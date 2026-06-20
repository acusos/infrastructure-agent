import subprocess


def get_docker_status():

    output = subprocess.check_output(
        [
            "docker",
            "ps",
            "--format",
            "{{.Names}}"
        ],
        text=True
    )

    containers = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    return {
        "running_containers": len(containers),
        "containers": containers,
    }
