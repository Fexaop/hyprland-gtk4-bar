import socket

# Simple UDP receiver
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', 6942))

print("Listening for broadcasts on port 6942...")
while True:
    data, addr = sock.recvfrom(1024)
    print(f"Received from {addr}: {data.decode('utf-8')}")
print("Done")