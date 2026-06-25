import psutil


def get_memory_status():

    mem = psutil.virtual_memory()

    return {
        "total_gb": round(mem.total / 1024**3, 1),
        "available_gb": round(mem.available / 1024**3, 1),
        "used_gb": round(mem.used / 1024**3, 1),
        "usage_percent": mem.percent,
    }
