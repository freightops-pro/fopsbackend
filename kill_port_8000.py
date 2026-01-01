import psutil

killed = []
for proc in psutil.process_iter(['pid', 'name']):
    try:
        connections = proc.connections()
        for conn in connections:
            if hasattr(conn, 'laddr') and conn.laddr.port == 8000:
                print(f"Killing process {proc.pid} ({proc.name()})")
                proc.kill()
                killed.append(proc.pid)
                break
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

if killed:
    print(f"Killed {len(killed)} processes: {killed}")
else:
    print("No processes found on port 8000")
