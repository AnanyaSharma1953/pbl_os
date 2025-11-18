# master.py
import socket
import json
import time

WORKERS = {
    "Worker-1": ("127.0.0.1", 5001),
    "Worker-2": ("127.0.0.1", 5002),
    # add more if needed
}

def send_to_worker(name, message, timeout=6):
    host, port = WORKERS[name]
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(message.encode())
            resp = s.recv(8192).decode(errors='ignore')
            return resp
    except Exception as e:
        return None  # caller interprets as unreachable

def get_all_metrics():
    metrics = {}
    for name in WORKERS:
        resp = send_to_worker(name, "METRICS")
        if not resp:
            metrics[name] = None
        else:
            try:
                metrics[name] = json.loads(resp.strip())
            except:
                metrics[name] = None
    return metrics

def choose_least_loaded():
    metrics = get_all_metrics()
    best = None
    best_score = float('inf')
    print("\n[DEBUG] Worker metrics:")
    for name, m in metrics.items():
        if m is None:
            print(f" → {name}: Unreachable")
            continue
        cpu = float(m.get("cpu", 999.0))
        mem = float(m.get("mem", 999.0))
        score = cpu * 0.6 + mem * 0.4
        print(f" → {name}: CPU={cpu:.1f}% MEM={mem:.1f}% SCORE={score:.2f}")
        if score < best_score:
            best_score = score
            best = name
    if best is None:
        print("❌ No available workers.")
    else:
        print(f"[Master] Selected {best}.")
    return best

def list_workers():
    for i, name in enumerate(WORKERS, 1):
        host, port = WORKERS[name]
        print(f"{i}. {name} ({host}:{port})")

def find_owner_of_pid(pid):
    """Ask each worker STATUS to see which has that PID in its tracked list."""
    for name in WORKERS:
        resp = send_to_worker(name, "STATUS")
        if resp is None:
            continue
        if str(pid) in resp:
            return name
    return None

def get_name_from_worker(owner, pid):
    resp = send_to_worker(owner, f"NAME {pid}")
    return resp.strip() if resp else None

def main():
    print("Available Workers:")
    list_workers()
    print("\nMaster Ready\nCommands: RUN <cmd> [--auto], STATUS ALL, STATUS <worker>, METRICS ALL, KILL <pid>, MIGRATE <pid>, EXIT")

    while True:
        cmd = input("\nEnter command: ").strip()
        if not cmd:
            continue

        if cmd.upper() == "EXIT":
            print("Master exiting.")
            break

        if cmd.upper() == "METRICS ALL":
            metrics = get_all_metrics()
            print("\n=== Worker Metrics ===")
            for name, m in metrics.items():
                if m:
                    print(f"{name}: CPU={m['cpu']:.1f}% MEM={m['mem']:.1f}% PROCS={m['procs']}")
                else:
                    print(f"{name}: Unreachable")
            continue

        if cmd.upper() == "STATUS ALL":
            print("\n=== Cluster Status ===")
            for name in WORKERS:
                resp = send_to_worker(name, "STATUS")
                if resp is None:
                    print(f"\n[{name}] Unreachable")
                else:
                    print(f"\n[{name}]\n{resp.strip()}")
            continue

        if cmd.upper().startswith("RUN"):
            # RUN <cmd> [--auto]
            parts = cmd.split()
            if "--auto" in parts:
                # extract real command (strip --auto)
                parts = [p for p in parts if p != "--auto"]
                if len(parts) < 2:
                    print("❌ Provide a command to run.")
                    continue
                actual_cmd = " ".join(parts[1:])
                target = choose_least_loaded()
                if not target:
                    continue
                print(f"[Master] Sending RUN to {target}: {actual_cmd}")
                resp = send_to_worker(target, f"RUN {actual_cmd}")
                print(f"[{target}] {resp.strip() if resp else 'No response'}")
            else:
                # interactive pick
                parts = cmd.split(" ", 1)
                if len(parts) < 2:
                    print("❌ Provide a command to run.")
                    continue
                actual_cmd = parts[1]
                print("Select worker:")
                list_workers()
                try:
                    i = int(input("Worker number: ").strip())
                    target = list(WORKERS.keys())[i-1]
                except:
                    print("Invalid selection.")
                    continue
                resp = send_to_worker(target, f"RUN {actual_cmd}")
                print(f"[{target}] {resp.strip() if resp else 'No response'}")
            continue

        if cmd.upper().startswith("KILL"):
            parts = cmd.split()
            if len(parts) < 2:
                print("❌ Provide PID")
                continue
            pid = parts[1]
            # ask user which worker to send or try to find owner
            owner = find_owner_of_pid(pid)
            if owner:
                print(f"Found owner: {owner}. Sending KILL...")
                resp = send_to_worker(owner, f"KILL {pid}")
                print(f"[{owner}] {resp.strip() if resp else 'No response'}")
            else:
                print("Owner not found automatically. Pick a worker:")
                list_workers()
                try:
                    i = int(input("Worker number: ").strip())
                    target = list(WORKERS.keys())[i-1]
                    resp = send_to_worker(target, f"KILL {pid}")
                    print(f"[{target}] {resp.strip() if resp else 'No response'}")
                except:
                    print("Invalid selection.")
            continue

        if cmd.upper().startswith("MIGRATE"):
            parts = cmd.split()
            if len(parts) < 2:
                print("❌ Provide PID")
                continue
            pid = parts[1]
            # find owner
            owner = find_owner_of_pid(pid)
            if not owner:
                print(f"⚠️ PID {pid} not found on tracked lists. Attempting KILL on all and restart on least loaded.")
                name_to_run = None
            else:
                # ask owner for process name
                name_resp = get_name_from_worker(owner, pid)
                if not name_resp or name_resp.startswith("❌"):
                    print(f"❌ Could not fetch process name from {owner}: {name_resp}")
                    name_to_run = None
                else:
                    name_to_run = name_resp.strip()
            # choose target (least loaded)
            target = choose_least_loaded()
            if not target:
                continue
            # instruct owner to kill
            if owner:
                kresp = send_to_worker(owner, f"MIGRATE {pid} --to {target}")
                print(f"[{owner}] {kresp.strip() if kresp else 'No response'}")
            else:
                # try to kill pid on all workers (best effort)
                for name in WORKERS:
                    send_to_worker(name, f"KILL {pid}")
            # restart on target using name_to_run or default notepad
            if name_to_run:
                print(f"[Master] Restarting '{name_to_run}' on {target}")
                rresp = send_to_worker(target, f"RUN {name_to_run}")
                print(f"[{target}] {rresp.strip() if rresp else 'No response'}")
            else:
                print(f"[Master] No process name available; starting default notepad on {target}")
                rresp = send_to_worker(target, "RUN notepad")
                print(f"[{target}] {rresp.strip() if rresp else 'No response'}")
            continue

        print("❗ Unknown or unsupported command.")

if __name__ == "__main__":
    main()
