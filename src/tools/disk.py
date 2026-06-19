import subprocess

def get_disk_status():
    return subprocess.check_output(
        ["df", "-h"],
        text=True
    )
