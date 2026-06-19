import subprocess


def get_container_logs(container_name, lines=50):

    try:

        output = subprocess.check_output(
            [
                "docker",
                "logs",
                "--tail",
                str(lines),
                container_name
            ],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10
        )

        return output

    except Exception as e:

        return str(e)

