import subprocess


def get_failed_services():

    try:

        output = subprocess.check_output(
            [
                "systemctl",
                "--failed",
                "--no-pager"
            ],
            text=True
        )

        return output

    except Exception as e:

        return f"Error: {e}"
