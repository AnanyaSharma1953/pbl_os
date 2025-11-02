import socket
import subprocess
import psutil
import getpass
import os

print("[WORKER RUNNING AS USER]:", getpass.getuser())
print("[DEBUG] Worker Session ID:", os.getpid(), "→", psutil.Process(os.getpid()).username())

HOST = '127.0.0.1'
PORT = 5001
started_pids = []

# --- Utility: Fetch all visible processes safely ---
def get_all_processes():
    """Return top processes including GUI-based apps from the user session."""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username', 'nice']):
            try:
                name = proc.info.get('name') or "Unknown"
                user = proc.info.get('username') or "N/A"
                cpu = proc.info.get('cpu_percent') or 0.0
                mem = proc.info.get('memory_percent') or 0.0
                prio = proc.info.get('nice')
                prio_str = str(prio) if prio is not None else "N/A"
                processes.append(
                    f"PID: {proc.pid:<6} | NAME: {name[:20]:<20} | USER: {user:<25} "
                    f"| CPU: {cpu:>5.1f}% | MEM: {mem:6.2f}% | PRIORITY: {prio_str}"
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # --- Include GUI apps from user's desktop session ---
        gui_output = subprocess.check_output('tasklist', shell=True).decode(errors='ignore')
        gui_lines = [line for line in gui_output.splitlines() if any(app in line.lower() 
                      for app in ["notepad.exe", "explorer.exe", "mspaint.exe", "calc.exe", "wordpad.exe"])]
        gui_section = "\n--- GUI Applications Detected ---\n" + ("\n".join(gui_lines) if gui_lines else "None")

        return "=== System-Wide Processes (with GUI) ===\n" + "\n".join(processes[:30]) + gui_section

    except Exception as e:
        return f"[Error fetching processes: {e}]"

# --- Return processes started by this worker ---
def get_local_processes():
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

# --- Priority fetch helper ---
def get_priority_level(pid):
    try:
        proc = psutil.Process(pid)
        return proc.nice()
    except Exception:
        return None

# --- Core Worker Socket ---
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

                # RUN command
                if data.startswith("RUN"):
                    cmd = data.split(" ", 1)[1]
                    try:
                        process = subprocess.Popen(cmd, shell=True)
                        started_pids.append(process.pid)
                        response = f"✅ Started '{cmd}' with PID {process.pid} (Tracked)"
                    except Exception as e:
                        response = f"❌ Error: {e}"

                # STATUS command
                elif data.startswith("STATUS"):
                    if "ALL" in data.upper():
                        response = "=== System-Wide Processes (with GUI) ===\n" + get_all_processes()
                    else:
                        response = get_local_processes()

                # KILL command
                # -------------------- KILL --------------------
                elif data.startswith("KILL"):
                    try:
                        pid = int(data.split(" ")[1])
                        proc = psutil.Process(pid)
                        pname = proc.name().lower()

        # 🛑 Define critical Windows processes that should never be killed
                        CRITICAL_PROCESSES = [
            "explorer.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
            "services.exe", "lsass.exe", "smss.exe", "system"
        ]

        # Block critical processes
                        if pname in CRITICAL_PROCESSES:
                            response = f"⚠️ {pname} is a critical system process and cannot be terminated for safety."
        
                        else:
                            priority = get_priority_level(pid)
            
            # Check if process has high priority
                            if priority is not None and priority >= 8:
                                conn.sendall(f"⚠️ Process {pid} ({pname}) has HIGH priority. Are you sure? (yes/no): ".encode())
                                confirmation = conn.recv(1024).decode().strip().lower()
                                if confirmation != "yes":
                                    response = f"❎ Kill command for {pid} cancelled by user."
                                    conn.sendall(response.encode())
                                    continue

            # Attempt to terminate the process safely
                            proc.terminate()
                            proc.wait(timeout=3)

                            response = f"💀 Process {pid} ({pname}) terminated successfully."
                            if pid in started_pids:
                                started_pids.remove(pid)

                    except psutil.NoSuchProcess:
                        response = f"❌ Process {pid} not found."
                    except psutil.AccessDenied:
                        response = f"🚫 Access Denied: Cannot terminate process {pid} ({pname}). Try running as Administrator."
                    except Exception as e:
                        response = f"⚠️ Error terminating process: {e}"

                elif data.upper() == "EXIT":
                    response = "👋 Worker shutting down..."
                    conn.sendall(response.encode())
                    break
                else:
                    response = "❗ Invalid command."

                conn.sendall(response.encode())
