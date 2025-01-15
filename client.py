import socket
import struct
import threading
import time
import sys

# Fixed broadcast port (should be configurable, not hardcoded for flexibility)
BROADCAST_PORT = 12345


# Function to listen for UDP offers
def listen_for_offers():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", BROADCAST_PORT))
    print(f"\033[94mClient started, listening for offer requests on UDP port {BROADCAST_PORT}...\033[0m")

    while True:
        try:
            data, server_address = udp_socket.recvfrom(1024)
            if validate_offer(data):
                print(f"\033[92mOffer received from {server_address[0]}\033[0m")
                process_offer(data, server_address)
        except KeyboardInterrupt:
            print("\033[91mClient shutting down...\033[0m")
            udp_socket.close()
            sys.exit(0)
        except Exception as e:
            print(f"\033[91mError receiving UDP packet: {e}\033[0m")


# Validate the offer packet
def validate_offer(data):
    try:
        magic_cookie, message_type, udp_port, tcp_port = struct.unpack("!IBHH", data)
        return magic_cookie == 0xabcddcba and message_type == 0x2
    except struct.error:
        return False


# Process the offer and prompt the user
def process_offer(data, server_address):
    _, _, udp_port, tcp_port = struct.unpack("!IBHH", data)
    print(f"\033[94mConnecting to server at {server_address[0]} (TCP: {tcp_port}, UDP: {udp_port})\033[0m")

    # Prompt user for test parameters
    try:
        file_size = int(input("\033[93mEnter the file size to download (bytes): \033[0m"))
        num_tcp_connections = int(input("\033[93mEnter the number of TCP connections: \033[0m"))
        num_udp_connections = int(input("\033[93mEnter the number of UDP connections: \033[0m"))

        # Start TCP and UDP connections
        threads = []
        for _ in range(num_tcp_connections):
            t = threading.Thread(target=tcp_request, args=(server_address[0], tcp_port, file_size), daemon=True)
            t.start()
            threads.append(t)

        for _ in range(num_udp_connections):
            t = threading.Thread(target=udp_request, args=(server_address[0], udp_port, file_size), daemon=True)
            t.start()
            threads.append(t)

        # Wait for all threads to complete before returning to listen for offers
        for t in threads:
            t.join()

        print("\033[92mAll transfers completed. Returning to listen for offers...\033[0m")
    except ValueError:
        print("\033[91mInvalid input. Please enter valid integers for file size and connections.\033[0m")


# Handle TCP transfers
# Handle TCP transfers
def tcp_request(server_ip, server_port, file_size):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((server_ip, server_port))
            tcp_socket.sendall(f"{file_size}\n".encode())
            print(f"\033[92mTCP connection established with {server_ip}:{server_port}\033[0m")

            start_time = time.time()
            total_received = 0

            while total_received < file_size:
                data = tcp_socket.recv(1024)
                if not data:
                    break
                total_received += len(data)

            end_time = time.time()
            duration = max(end_time - start_time, 0.001)  # Minimum duration of 1 millisecond
            speed = total_received / duration
            print(f"\033[96mTCP transfer finished: Total Time = {duration:.3f}s, Speed = {speed:.2f} bytes/s\033[0m")
    except Exception as e:
        print(f"\033[91mTCP request failed: {e}\033[0m")


# Handle UDP transfers
def udp_request(server_ip, server_port, file_size):
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        request_message = struct.pack("!IBQ", 0xabcddcba, 0x3, file_size)  # Magic cookie, request type, file size
        udp_socket.sendto(request_message, (server_ip, server_port))
        print(f"\033[92mUDP request sent to {server_ip}:{server_port}\033[0m")

        start_time = time.time()
        total_received = 0
        received_packets = 0
        expected_packets = file_size // 1024  # Assuming 1 KB packets

        while received_packets < expected_packets:
            try:
                udp_socket.settimeout(2)  # Timeout for receiving response
                data, _ = udp_socket.recvfrom(1024)
                total_received += len(data)
                received_packets += 1
            except socket.timeout:
                print("\033[93mTimeout while waiting for UDP packet. Stopping reception.\033[0m")
                break

        end_time = time.time()
        duration = end_time - start_time
        speed = total_received / duration if duration > 0 else 0
        packet_loss = (1 - (received_packets / expected_packets)) * 100 if expected_packets > 0 else 100
        print(f"\033[96mUDP transfer finished: Total Time = {duration:.2f}s, "
              f"Speed = {speed:.2f} bytes/s, Packet Loss = {packet_loss:.2f}%\033[0m")
    except Exception as e:
        print(f"\033[91mUDP request failed: {e}\033[0m")
    finally:
        udp_socket.close()


if __name__ == "__main__":
    listen_for_offers()
