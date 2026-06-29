import socket

def check_tcp(host, port, timeout=5):
    """Check if a TCP port is open on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.gaierror, socket.error):
        return False

def check_server_ports(server):
    """Check all configured ports for a server."""
    name = server["name"]
    host = server["host"]
    ports = server.get("ports", [])
    timeout = server.get("timeout", 5)

    results = {}
    for port in ports:
        results[port] = check_tcp(host, port, timeout)

    all_up = all(results.values())

    if all_up:
        return f"{name} healthy (all ports open)"
    else:
        failed = [p for p, s in results.items() if not s]
        return f"{name} unhealthy (ports down: {failed})"

def check_all_servers(servers):
    """Check all configured servers."""
    results = {}
    for server in servers:
        results[server["name"]] = check_server_ports(server)
    return results
