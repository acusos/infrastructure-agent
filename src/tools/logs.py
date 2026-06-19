import subprocess


def get_recent_errors():

    try:

        output = subprocess.check_output(
            [
                "journalctl",
                "-p",
                "err",
                "-n",
                "50",
                "--no-pager"
            ],
            text=True
        )

        lines = []

        for line in output.splitlines():

            if (
                "veth" in line
                or "br-" in line
                or "networkctl" in line
            ):
                continue

            lines.append(line)

        if not lines:
            return "No significant errors found."

        return "\n".join(lines)

    except Exception as e:

        return str(e)
