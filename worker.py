import socket
import subprocess
import psutil
import os

HOST = '127.0.0.1'   # Localhost
PORT = 5001          # Worker listening port

started_pids = []  # Processes started by this worker


def get_all_processes():
    """Return top 10 system processes."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'nice']):
        try:
            processes.append(
                f"PID: {proc.info['pid']:<6} | NAME: {proc.info['name'][:20]:<20} "
                f"| CPU: {proc.info['cpu_percent']:>5}% | MEM: {proc.info['memory_percent']:.2f}% | PRIORITY: {proc.info['nice']}"
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "\n".join(processes[:10])


def get_local_processes():
    """Return processes created by this worker."""
    if not started_pids:
        return "No tracked processes are currently running."

    response = "=== Processes Started by Worker ===\n"
    for pid in started_pids:
        try:
            proc = psutil.Process(pid)
            response += (
                f"PID: {pid:<6} | NAME: {proc.name():<20} "
                f"| CPU: {proc.cpu_percent()}% | MEM: {proc.memory_percent():.2f}% | PRIORITY: {proc.nice()}\n"
            )
        except psutil.NoSuchProcess:
            response += f"PID: {pid:<6} | [Terminated]\n"
    return response


def get_priority_level(pid):
    """Return priority level for a process."""
    try:
        proc = psutil.Process(pid)
        return proc.nice()
    except Exception:
        return None


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"[WORKER] Listening on {HOST}:{PORT}...")

    while True:
        conn, addr = s.accept()
        print(f"[WORKER] Connected by {addr}")
        with conn:
            while True:
                data = conn.recv(1024).decode().strip()
                if not data:
                    break

                # -------------------- RUN --------------------
                if data.startswith("RUN"):
                    cmd = data.split(" ", 1)[1]
                    try:
                        if "\\" in cmd or cmd.lower() in ["notepad", "write", "explorer"]:
                            process = subprocess.Popen([cmd], shell=False)
                        elif cmd.lower().startswith("ping") or cmd.lower() in ["cmd", "ipconfig", "python"]:
                            process = subprocess.Popen(["cmd", "/c", "start", cmd], shell=True)
                        else:
                            process = subprocess.Popen(f"start {cmd}", shell=True)

                        started_pids.append(process.pid)
                        response = (
                            f"✅ Started process '{cmd}' with PID {process.pid}\n"
                            f"(Tracked for safe termination)"
                        )
                    except FileNotFoundError:
                        response = f"❌ Error: Command '{cmd}' not found."
                    except Exception as e:
                        response = f"❌ Error starting process: {e}"

                # -------------------- STATUS --------------------
                elif data.startswith("STATUS"):
                    if "ALL" in data.upper():
                        response = "=== Top System Processes ===\n" + get_all_processes()
                    else:
                        response = get_local_processes()

                # -------------------- KILL --------------------
                elif data.startswith("KILL"):
                    try:
                        pid = int(data.split(" ")[1])
                        priority = get_priority_level(pid)
                        if priority is None:
                            response = f"❌ Process {pid} not found."
                        else:
                            # Check if high priority
                            if priority >= 8:  # High or above normal
                                conn.sendall(f"⚠️ Process {pid} has HIGH priority. Are you sure? (yes/no): ".encode())
                                confirmation = conn.recv(1024).decode().strip().lower()
                                if confirmation != "yes":
                                    response = "❎ Kill command cancelled by user."
                                    conn.sendall(response.encode())
                                    continue

                            result = os.system(f"taskkill /PID {pid} /F >nul 2>&1")
                            if result == 0:
                                response = f"💀 Process {pid} terminated successfully."
                                if pid in started_pids:
                                    started_pids.remove(pid)
                            else:
                                response = f"⚠️ Could not terminate process {pid}."
                    except Exception as e:
                        response = f"❌ Error: {e}"

                # -------------------- EXIT --------------------
                elif data.upper() == "EXIT":
                    response = "👋 Worker shutting down..."
                    conn.sendall(response.encode())
                    break

                # -------------------- INVALID --------------------
                else:
                    response = "❗ Invalid command received."

                conn.sendall(response.encode())
