import subprocess

def get_docker_status():

    return subprocess.check_output(
        [
            "docker",
            "ps",
            "--format",
            "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ],
        text=True
    )
