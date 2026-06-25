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

        important = []

        for line in output.splitlines():

            if (
                "ValueError:" in line
                or "Exception:" in line
                or "ERROR" in line
            ):
                important.append(line)

        if important:

            return "\n".join(important[-5:])

        return "\n".join(output.splitlines()[-10:])

    except Exception as e:

        return str(e)
