# worker.py
import socket
import subprocess
import psutil
import getpass
import os
import sys
import time
import json

# config
HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
started_pids = []  # list of PIDs this worker is actively tracking

print(f"[WORKER RUNNING AS USER]: {getpass.getuser()}")
print(f"[DEBUG] Worker Session PID: {os.getpid()} | PORT: {PORT}")
print(f"[WORKER] Listening on {HOST}:{PORT}...")

# ---------------- helpers ----------------

def get_metrics():
    """Return a JSON serializable metrics dict."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory().percent
        procs = len(psutil.pids())
        return {"cpu": cpu, "mem": mem, "procs": procs}
    except Exception as e:
        return {"cpu": 999.0, "mem": 999.0, "procs": 0, "error": str(e)}

def prune_started_pids():
    """Remove dead PIDs from started_pids to avoid stale entries."""
    for pid in started_pids[:]:
        if not psutil.pid_exists(pid):
            started_pids.remove(pid)

def get_local_processes():
    prune_started_pids()
    if not started_pids:
        return "No active processes."
    out = "=== Processes Started by Worker ===\n"
    for pid in started_pids:
        try:
            p = psutil.Process(pid)
            out += f"PID: {pid:<6} | NAME: {p.name():<20} | STATUS: {p.status()}\n"
        except psutil.NoSuchProcess:
            out += f"PID: {pid:<6} | [Terminated]\n"
    return out

def find_new_pid_after_launch(exe_name, before_pids, timeout=5.0):
    """Poll to find a new PID with name exe_name not in before_pids. Return PID or None."""
    deadline = time.time() + timeout
    exe_name = exe_name.lower()
    while time.time() < deadline:
        candidates = []
        for p in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                name = (p.info.get('name') or "").lower()
                pid = p.info.get('pid')
                if name == exe_name and pid not in before_pids:
                    candidates.append((p.info.get('create_time', 0), pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if candidates:
            # choose newest
            candidates.sort(reverse=True)
            return candidates[0][1]
        time.sleep(0.15)
    return None

def guess_exe_name_from_cmd(cmd):
    """Return likely executable name from command string (e.g. 'notepad' -> 'notepad.exe')."""
    first = cmd.strip().split()[0]
    # if user passed path, take basename
    exe = os.path.basename(first)
    if not exe.lower().endswith('.exe'):
        exe = exe + ".exe"
    return exe

def safe_run_and_get_pid(cmd):
    """
    Start cmd so GUI appears in desktop. If GUI, find actual process PID and return it.
    Otherwise return subprocess.Popen.pid.
    """
    # detect GUI-like apps by common names
    lower = cmd.lower()
    gui_tokens = ["notepad", "calc", "mspaint", "explorer", "wordpad"]
    is_gui = any(tok in lower for tok in gui_tokens)

    if is_gui:
        exe_name = guess_exe_name_from_cmd(cmd)
        before = set(psutil.pids())
        # Use Windows start to open in interactive desktop
        # start "" <cmd>  (use empty title)
        try:
            subprocess.Popen(f'start "" {cmd}', shell=True)
        except Exception as e:
            return None, f"❌ Error launching GUI: {e}"
        # find new PID for exe_name
        new_pid = find_new_pid_after_launch(exe_name, before_pids=before, timeout=5.0)
        if new_pid:
            return new_pid, f"✅ Started GUI '{cmd}' with PID {new_pid}"
        else:
            return None, f"⚠️ Started '{cmd}' but could not detect its PID (it may have exited immediately)."
    else:
        # non-gui: launch normally and return the pid of Popen
        try:
            p = subprocess.Popen(cmd, shell=True)
            # Wait a tiny bit and verify it's alive
            time.sleep(0.1)
            if psutil.pid_exists(p.pid):
                return p.pid, f"✅ Started background process '{cmd}' with PID {p.pid}"
            else:
                return None, f"⚠️ Process '{cmd}' exited immediately."
        except Exception as e:
            return None, f"❌ Error launching process: {e}"

def safe_kill(pid):
    """Kill by PID using taskkill for GUI and fallback to terminate - return message."""
    try:
        p = psutil.Process(pid)
        pname = p.name().lower()
        # critical processes safeguard
        critical = {"explorer.exe", "csrss.exe", "wininit.exe", "system", "services.exe", "lsass.exe"}
        if pname in critical:
            return f"⚠️ {pname} is a critical system process and won't be terminated."
        # Use taskkill to ensure GUI windows close
        subprocess.run(f"taskkill /PID {pid} /F /T", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # remove from tracking if present
        if pid in started_pids:
            started_pids.remove(pid)
        return f"💀 Process {pid} ({pname}) terminated successfully."
    except psutil.NoSuchProcess:
        return f"❌ Process {pid} not found."
    except psutil.AccessDenied:
        return f"🚫 Access Denied: need higher privileges to kill {pid}."
    except Exception as e:
        return f"⚠️ Kill error: {e}"

# ---------------- server loop ----------------
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    while True:
        conn, addr = s.accept()
        with conn:
            # simple protocol: receive command string, respond with text
            try:
                while True:
                    data = conn.recv(4096).decode(errors='ignore').strip()
                    if not data:
                        break

                    # RUN <cmd>
                    if data.upper().startswith("RUN"):
                        parts = data.split(" ", 1)
                        if len(parts) < 2 or not parts[1].strip():
                            conn.sendall("❌ No command provided.\n".encode())
                            continue
                        cmd = parts[1].strip()
                        pid, msg = safe_run_and_get_pid(cmd)
                        if pid:
                            started_pids.append(pid)
                        conn.sendall((msg + "\n").encode())

                    # STATUS
                    elif data.upper().startswith("STATUS"):
                        resp = get_local_processes()
                        conn.sendall((resp + "\n").encode())

                    # METRICS
                    elif data.upper().startswith("METRICS"):
                        metrics = get_metrics()
                        conn.sendall((json.dumps(metrics) + "\n").encode())

                    # NAME <pid>
                    elif data.upper().startswith("NAME"):
                        parts = data.split()
                        if len(parts) < 2:
                            conn.sendall("❌ NAME requires a PID\n".encode())
                            continue
                        try:
                            pid = int(parts[1])
                            if not psutil.pid_exists(pid):
                                conn.sendall(f"❌ PID {pid} not found\n".encode())
                                continue
                            name = psutil.Process(pid).name()
                            conn.sendall((name + "\n").encode())
                        except Exception as e:
                            conn.sendall((f"❌ Error getting name: {e}\n").encode())

                    # KILL <pid>
                    elif data.upper().startswith("KILL"):
                        parts = data.split()
                        if len(parts) < 2:
                            conn.sendall("❌ KILL requires PID\n".encode())
                            continue
                        try:
                            pid = int(parts[1])
                            msg = safe_kill(pid)
                            conn.sendall((msg + "\n").encode())
                        except Exception as e:
                            conn.sendall((f"❌ Invalid PID: {e}\n").encode())

                    # MIGRATE <pid> --to <target>
                    elif data.upper().startswith("MIGRATE"):
                        # we only simulate on worker side: accept request, kill local pid if matches
                        # expected format: MIGRATE <pid> --to <workerName>
                        parts = data.split()
                        if len(parts) < 2:
                            conn.sendall("❌ MIGRATE requires PID\n".encode())
                            continue
                        try:
                            pid = int(parts[1])
                            # kill locally if exists
                            if psutil.pid_exists(pid):
                                msg = safe_kill(pid)
                                conn.sendall((f"[Worker] {msg}\n").encode())
                            else:
                                conn.sendall((f"[Worker] PID {pid} not found locally\n").encode())
                        except Exception as e:
                            conn.sendall((f"❌ MIGRATE error: {e}\n").encode())

                    # EXIT
                    elif data.upper() == "EXIT":
                        conn.sendall("👋 Worker shutting down...\n".encode())
                        conn.close()
                        os._exit(0)

                    else:
                        conn.sendall("❗ Invalid command.\n".encode())

            except Exception as e:
                # keep worker alive on client errors
                print(f"[WORKER ERROR] {e}")
                try:
                    conn.sendall((f"[ERROR] {e}\n").encode())
                except:
                    pass
                continue
