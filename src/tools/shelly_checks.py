import requests

SHWATT_THRESHOLD = 800  # Watts

def check_shelly_power(name, host, timeout=10):
    """Check Shelly 1PM Gen4 power consumption via RPC API."""
    try:
        url = f"http://{host}/rpc/Shelly.GetStatus"
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()

        if "switch:0" in data and "apower" in data["switch:0"]:
            wattage = data["switch:0"]["apower"]
        else:
            return f"shelly_{name}: no power data in response"

        if wattage >= SHWATT_THRESHOLD:
            return f"shelly_{name}: {wattage}W (ALERT >= {SHWATT_THRESHOLD}W)"
        else:
            return f"shelly_{name}: {wattage}W"
    except requests.exceptions.RequestException as e:
        return f"shelly_{name}: unreachable ({e})"

def check_all_shellys(shelly_configs):
    """Check all configured Shelly devices."""
    results = {}
    for device in shelly_configs:
        name = device["name"]
        host = device["host"]
        timeout = device.get("timeout", 10)
        results[name] = check_shelly_power(name, host, timeout)
    return results
