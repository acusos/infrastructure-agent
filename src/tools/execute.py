import subprocess


def run_command(command: str):

    try:

        result = subprocess.check_output(
            command,
            shell=True,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30
        )

        return result

    except Exception as e:

        return str(e)
