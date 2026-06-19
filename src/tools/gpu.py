import subprocess

def get_gpu_status():

    output = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits"
        ],
        text=True
    )

    name, used, total, temp = [x.strip() for x in output.split(",")]

    return {
        "name": name,
        "memory_used_mib": int(used),
        "memory_total_mib": int(total),
        "memory_free_mib": int(total) - int(used),
        "temperature_c": int(temp)
    }

    return f"""
GPU: {name}
Used VRAM: {used:,} MiB
Total VRAM: {total:,} MiB
Free VRAM: {total-used:,} MiB
Temperature: {temp}°C
"""
