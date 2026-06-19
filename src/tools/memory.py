import psutil

def get_memory_status():

    mem = psutil.virtual_memory()

    return f"""
Total RAM: {mem.total / 1024**3:.1f} GB
Available RAM: {mem.available / 1024**3:.1f} GB
Used RAM: {mem.used / 1024**3:.1f} GB
Usage: {mem.percent}%
"""
