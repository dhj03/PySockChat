import sys
from socket import *
import threading
from random import randint
from time import sleep

def main():
    # Prepare terminal arguments
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} server_port")
        exit(1)

    server_port = int(sys.argv[1])

    # Create a socket and connect to the server
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect(('localhost', server_port))
    # Create a socket for welcoming private messaging connections
    global pm_welcome_socket
    pm_welcome_socket = socket(AF_INET, SOCK_STREAM)

    global username
    username = None

    try:
        # Attempt to authenticate client
        while True:
            inbound = server_socket.recv(1024).decode()

            if inbound == "":
                server_socket.close()
                return

            print(inbound, end='')

            if inbound.startswith("Welcome"):
                break

            outbound = input().replace(' ', '')
            if username is None:
                username = outbound
            server_socket.send(outbound.encode())

        # Authentication successful, declare a few globals for keeping status
        global online; global confirm; global confirm_active; global pms; global pm_port
        online = True
        confirm = None
        confirm_active = False
        pms = {}

        # Create a server socket for private messaging, with random port numbers
        while True:
            try:
                pm_port = randint(16385, 65536)
                pm_welcome_socket.bind(('localhost', pm_port))
                pm_welcome_socket.listen(1)
            except OSError:
                pass
            else:
                break

        # Setup a thread for receiving packets, and continuously send commands to the server
        threading.Thread(target=rcv_from_server, args=(server_socket,)).start()
        send_commands(server_socket)
        # The function will exit once logged off or disconnected otherwise

        for peer_socket in pms.values():
            peer_socket.shutdown(SHUT_RDWR)

        pm_welcome_socket.close()
        server_socket.close()

    except KeyboardInterrupt:
        pass

def send_commands(server_socket):

    global online
    global confirm
    global confirm_active

    while True:
        outbound = input()

        if not online or outbound == "logout":
            break

        if outbound == "y":
            if confirm_active:
                confirm = True
            else:
                print("Error: Invalid command")
            continue
        if outbound == "n":
            if confirm_active:
                confirm = False
            else:
                print("Error: Invalid command")
            continue

        if outbound.startswith("startprivate "):
            peer_name = outbound[13:]
            if peer_name == "":
                print("Usage: startprivate <user>")
            elif pms.get(peer_name) is not None:
                print(f"Error: Private messaging to {peer_name} is already enabled")

        elif outbound.startswith("private "):
            args = outbound.split(' ', 2)
            if len(args) < 3:
                print("Usage: private <user> <message>")
            elif pms.get(args[1]) is None:
                print(f"Error: Private messaging to {args[1]} is not enabled")
            else:
                pms[args[1]].send(f"{username}(private): {args[2]}".encode())
            outbound = "private"

        elif outbound.startswith("stopprivate "):
            peer_name = outbound[12:]
            if peer_name == "":
                print("Usage: stopprivate <user>")
            elif pms.get(peer_name) is None:
                print(f"Error: Private messaging to {peer_name} is not enabled")
            else:
                pms[peer_name].shutdown(SHUT_RDWR)
            outbound = "private"

        elif outbound.startswith("respprivate "):
            # Directly executing this command is illegal
            continue

        server_socket.send(outbound.encode())

    server_socket.shutdown(SHUT_RDWR)

def rcv_from_server(server_socket):

    global online
    global confirm
    global confirm_active
    try:
        while True:
            inbound = server_socket.recv(1024).decode()

            if inbound == "":
                break

            # reqprivate <username>
            if inbound.startswith("reqprivate "):
                args = inbound[:-1].split(' ', 1)

                confirm_active = True
                print(f"{args[1]} wants to start a private chat. Reply with \"y\" or \"n\"")
                while confirm is None:
                    sleep(0.05)

                if confirm:
                    confirm = None; confirm_active = False
                    # Listen from pm_welcome_socket for a connection to start a PM
                    threading.Thread(target=rcv_pms_as_server,
                        args=(args[1], pm_welcome_socket)).start()
                    server_socket.send(f"respprivate {args[1]} {pm_port}".encode())
                else:
                    confirm = None; confirm_active = False
                    server_socket.send(f"respprivate {args[1]} None".encode())
                continue

            # initprivate <username> <port>
            if inbound.startswith("initprivate "):
                args = inbound[:-1].split(' ', 2)

                print(f"{args[1]} accepted your private messaging request")
                # Create a new socket and connect to the pm port to start a PM
                threading.Thread(target=rcv_pms_as_client, args=(args[1], int(args[2]))).start()
                continue

            print(inbound, end='')

    except KeyboardInterrupt:
        pass

    online = False

def rcv_pms_as_server(peer_name, welcome_socket):
    try:
        # Give 10 seconds for the peer to connect to the server
        welcome_socket.settimeout(10)
        peer_socket = None
        peer_socket, address = welcome_socket.accept()
        # If connected
        welcome_socket.settimeout(None)
        pms[peer_name] = peer_socket

        while True:
            inbound = peer_socket.recv(1024).decode()
            if inbound == "":
                break
            print(inbound)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in private chat with {peer_name}: {e}")

    pms.pop(peer_name, None)
    if peer_socket is not None:
        peer_socket.close()
    if online:
        print(f"Closed private chat with {peer_name}")

def rcv_pms_as_client(peer_name, port):
    try:
        # Attempt to connect to the peer's PM server
        peer_socket = socket(AF_INET, SOCK_STREAM)
        peer_socket.connect(('localhost', port))
        pms[peer_name] = peer_socket

        while True:
            inbound = peer_socket.recv(1024).decode()
            if inbound == "":
                break
            print(inbound)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in private chat with {peer_name}: {e}")

    pms.pop(peer_name, None)
    peer_socket.close()
    if online:
        print(f"Closed private chat with {peer_name}")

if __name__ == "__main__":
    main()
