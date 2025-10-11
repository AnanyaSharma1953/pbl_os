import socket

WORKER_HOST = '127.0.0.1'
WORKER_PORT = 5001

print("\nAvailable commands:")
print("1. RUN <command>")
print("2. STATUS")
print("3. STATUS ALL")
print("4. KILL <pid>")
print("5. EXIT")

# keep socket open
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((WORKER_HOST, WORKER_PORT))
    print("\nConnected to Worker ✅")

    while True:
        cmd = input("\nEnter command: ").strip()
        if not cmd:
            continue

        s.sendall(cmd.encode())
        response = s.recv(4096).decode()

        # check if worker is asking for confirmation
        if "Are you sure?" in response:
            print("\n[WORKER RESPONSE]:\n", response)
            confirmation = input().strip().lower()
            s.sendall(confirmation.encode())  # send yes/no back
            response = s.recv(4096).decode()
            print("\n[WORKER RESPONSE]:\n", response)
        else:
            print("\n[WORKER RESPONSE]:\n", response)

        if cmd.upper() == "EXIT":
            print("\nClosing connection. Bye! 👋")
            break
