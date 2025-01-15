import socket
import struct
import threading
import time
import signal
import sys

# Global configuration
BROADCAST_PORT = 12345  # Fixed broadcast port
shutdown_flag = threading.Event()  # Graceful shutdown flag


def handle_tcp_speedtest(tcp_socket):
    while not shutdown_flag.is_set():
        try:
            tcp_socket.settimeout(1)  # Periodic timeout to check shutdown
            client_socket, client_address = tcp_socket.accept()
            print(f"\033[92mNew TCP client connected: {client_address}\033[0m")

            try:
                # Handle client request
                data = client_socket.recv(1024)
                if data:
                    file_size = int(data.decode().strip())
                    print(f"\033[94mClient requested TCP transfer of {file_size} bytes\033[0m")

                    total_sent = 0
                    chunk = b"A" * 1024  # 1 KB chunk
                    while total_sent < file_size:
                        client_socket.sendall(chunk)
                        total_sent += len(chunk)

                    print(f"\033[96mTCP: Sent {total_sent} bytes to {client_address}\033[0m")
            except Exception as e:
                print(f"\033[91mError handling TCP client {client_address}: {e}\033[0m")
            finally:
                client_socket.close()
        except socket.timeout:
            continue


def handle_udp_speedtest(udp_socket):
    while not shutdown_flag.is_set():
        try:
            udp_socket.settimeout(1)  # Timeout to periodically check the shutdown flag
            data, client_address = udp_socket.recvfrom(1024)

            try:
                # Parse UDP request
                magic_cookie, message_type, file_size = struct.unpack("!IBQ", data)
                if magic_cookie == 0xabcddcba and message_type == 0x3:
                    print(f"\033[92mValid UDP request from {client_address}\033[0m")

                    total_packets = (file_size + 1023) // 1024  # Number of 1 KB packets
                    for i in range(total_packets):
                        payload = struct.pack("!IBQQ", 0xabcddcba, 0x4, total_packets, i) + b"A" * 1024
                        udp_socket.sendto(payload[:1024], client_address)

                    print(f"\033[96mUDP: Sent {total_packets} packets to {client_address}\033[0m")
                else:
                    print(f"\033[93mInvalid UDP request from {client_address}\033[0m")
            except struct.error:
                print(f"\033[93mMalformed UDP request from {client_address}\033[0m")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"\033[91mError handling UDP requests: {e}\033[0m")


def broadcast_offers(broadcast_socket, udp_port, tcp_port):
    while not shutdown_flag.is_set():
        try:
            offer_message = struct.pack("!IBHH", 0xabcddcba, 0x2, udp_port, tcp_port)
            broadcast_socket.sendto(offer_message, ("<broadcast>", BROADCAST_PORT))
            print(f"\033[94mBroadcasting offer: UDP {udp_port}, TCP {tcp_port}\033[0m")
            time.sleep(1)
        except Exception as e:
            print(f"\033[91mError broadcasting offers: {e}\033[0m")


def signal_handler(sig, frame):
    print("\n\033[91mShutting down server...\033[0m")
    shutdown_flag.set()


def start_server():
    signal.signal(signal.SIGINT, signal_handler)

    # Broadcast socket setup
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # UDP socket setup
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(("0.0.0.0", 0))  # Dynamic UDP port
    udp_port = udp_socket.getsockname()[1]

    # TCP socket setup
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(("0.0.0.0", 0))  # Dynamic TCP port
    tcp_socket.listen(5)
    tcp_port = tcp_socket.getsockname()[1]

    print(f"\033[92mServer ready: Broadcast on UDP {BROADCAST_PORT}, UDP {udp_port}, TCP {tcp_port}\033[0m")

    # Start threads for broadcasting and handling requests
    threading.Thread(target=broadcast_offers, args=(broadcast_socket, udp_port, tcp_port), daemon=True).start()
    threading.Thread(target=handle_udp_speedtest, args=(udp_socket,), daemon=True).start()
    threading.Thread(target=handle_tcp_speedtest, args=(tcp_socket,), daemon=True).start()

    while not shutdown_flag.is_set():
        time.sleep(1)

    # Cleanup
    print("\033[93mClosing sockets...\033[0m")
    broadcast_socket.close()
    udp_socket.close()
    tcp_socket.close()


if __name__ == "__main__":
    start_server()
