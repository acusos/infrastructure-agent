import os
import time
import psutil

from src.tools.telegram_sender import send_telegram_message

from src.tools.container_check import (
    check_llamacpp,
    check_litellm,
    check_qdrant,
    check_open_webui,
)

from src.tools.service_states import (
    load_states,
    save_states,
)

from src.tools.auto_recovery import (
    recover_service,
)

from src.tools.snapshot import (
    save_snapshot,
)

from src.tools.tcp_checks import check_all_servers
from src.tools.memory import get_memory_status
from src.tools.shelly_checks import check_all_shellys

CHECK_INTERVAL = 30
SNAPSHOT_INTERVAL = 3600

CPU_THRESHOLD = 95
MEMORY_THRESHOLD = 95

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

LOCAL_SERVICES = {"llama-cpp", "litellm", "qdrant", "open-webui"}
METRIC_SERVICES = {"cpu", "memory", "disk", "network"}

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            import yaml
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Config load error: {e}")
        return {}

def get_current_states():
    return {
        "llama-cpp": check_llamacpp(),
        "litellm": check_litellm(),
        "qdrant": check_qdrant(),
        "open-webui": check_open_webui(),
    }

def get_server_states():
    config = load_config()
    servers = config.get("servers", [])
    if not servers:
        return {}
    return check_all_servers(servers)

def get_shelly_states():
    config = load_config()
    shellys = config.get("shellys", [])
    if not shellys:
        return {}
    return check_all_shellys(shellys)

def get_resource_states():
    states = {}

    cpu_percent = psutil.cpu_percent(interval=1)
    states["cpu"] = f"CPU: {cpu_percent}%{' (ALERT)' if cpu_percent >= CPU_THRESHOLD else ''}"

    mem = get_memory_status()
    mem_percent = mem["usage_percent"]
    states["memory"] = f"Memory: {mem_percent}% used ({mem['used_gb']}/{mem['total_gb']}GB){' (ALERT)' if mem_percent >= MEMORY_THRESHOLD else ''}"

    disk = psutil.disk_usage('/')
    states["disk"] = f"Disk: {disk.percent}% used ({disk.used / 1024**3:.1f}/{disk.total / 1024**3:.1f}GB){' (ALERT)' if disk.percent >= 95 else ''}"

    net = psutil.net_io_counters()
    states["network"] = f"Network: RX={net.bytes_recv / 1024**2:.1f}MB TX={net.bytes_sent / 1024**2:.1f}MB"

    return states

def is_healthy(status):
    return " healthy" in status

def is_alertable(service, status):
    if service in METRIC_SERVICES:
        return "ALERT" in status
    if service.startswith("shelly"):
        return "ALERT" in status
    return not is_healthy(status)

def is_recoverable(service):
    return service in LOCAL_SERVICES

def monitor():
    print("InfraBot Monitor Started")
    previous = {}
    last_snapshot = 0
    first_check = True

    while True:
        try:
            current = get_current_states()
            server_states = get_server_states()
            resource_states = get_resource_states()
            shelly_states = get_shelly_states()

            all_states = {
                **current,
                **server_states,
                **resource_states,
                **shelly_states,
            }

            for service, status in all_states.items():
                old_status = previous.get(service)
                old_alert = is_alertable(service, old_status) if old_status else False
                new_alert = is_alertable(service, status)

                if first_check and service not in METRIC_SERVICES and not service.startswith("shelly"):
                    continue

                if not old_alert and new_alert:
                    if is_recoverable(service):
                        send_telegram_message(
                            f"🚨 InfraBot Alert\n\n"
                            f"{service} unhealthy\n\n"
                            f"Attempting recovery..."
                        )
                        success, message = recover_service(service)
                        if success:
                            send_telegram_message(
                                f"⚠️ InfraBot Auto Recovery\n\n"
                                f"{message}"
                            )
                        else:
                            send_telegram_message(
                                f"🚨 InfraBot Critical\n\n"
                                f"{message}"
                            )
                    else:
                        send_telegram_message(
                            f"🚨 InfraBot Alert\n\n"
                            f"{service} unhealthy\n\n"
                            f"Status: {status}"
                        )

                elif old_alert and not new_alert:
                    send_telegram_message(
                        f"✅ InfraBot Recovery\n\n"
                        f"{service} healthy again"
                    )
                    print(f"{service} recovered")

            first_check = False

            now = time.time()
            if now - last_snapshot >= SNAPSHOT_INTERVAL:
                try:
                    result = save_snapshot()
                    print(result)
                    last_snapshot = now
                except Exception as e:
                    print(f"Snapshot error: {e}")

            save_states(all_states)
            previous = all_states
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor()
