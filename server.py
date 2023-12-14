import sys
from socket import *
import threading
from datetime import timezone, datetime
from time import sleep

def curr_time():
    return int(datetime.now().replace(tzinfo=timezone.utc).timestamp())

def main():
    # Prepare terminal arguments and global variables
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} server_port block_duration timeout")
        exit(1)

    server_port = int(sys.argv[1])

    global block_duration; global timeout;  global users

    block_duration = int(sys.argv[2])
    timeout = int(sys.argv[3])
    users = {}

    # Create a socket for welcoming clients at the specified port
    welcome_socket = socket(AF_INET, SOCK_STREAM)
    welcome_socket.bind(('localhost', server_port))
    welcome_socket.listen(1)

    # Continuously listen for new clients and starting new threads to handle their connection
    while True:
        try:
            client_socket, address = welcome_socket.accept()
            connection_thread = threading.Thread(target=manage_client, args=(client_socket,))
            connection_thread.start()
        except KeyboardInterrupt:
            break

    welcome_socket.close()

# Manage the connection with the client
def manage_client(conn_socket):
    try:
        conn_socket.settimeout(timeout)

        username = None; user = None
        username, user = authenticate(conn_socket)

        # Attempt to log the user in
        if user['online']:
            conn_socket.send(b"Your account is already logged in on another client.\n")
            raise Exception(f"{username} is already online")

        presence_broadcast(username, f"{username} logged in")
        conn_socket.send(b"Welcome!\n")
        user['online'] = True
        user['last_online'] = curr_time()

        # Start a thread to flush the message buffer for the client
        threading.Thread(target=flush_messages, args=(conn_socket, user)).start()
        # Listen for and respond to commands from the client
        run_commands(conn_socket, user, username)
        # The function will run until the connection ends

    except KeyboardInterrupt:
        pass
    except Exception as e:
        if str(e) == "timed out":
            conn_socket.send(b"You have been logged out for inactivity.\n")
        print(e)

    # Log the user out if they are logged in
    if username:
        user['online'] = False
        presence_broadcast(username, f"{username} logged out")

    conn_socket.close()

def run_commands(conn_socket, user, username):

    while True:
        inbound = conn_socket.recv(1024).decode()
        # Reset the timeout to the original, specified value
        # It will be overwritten if the command entered is invalid
        conn_socket.settimeout(timeout)

        if inbound == "":
            return
        elif inbound.startswith("message "):
            message_user(conn_socket, user, username, inbound)
        elif inbound.startswith("broadcast "):
            broadcast(conn_socket, user, username, inbound)
        elif inbound == "whoelse":
            whoelse(conn_socket, user, username)
        elif inbound.startswith("whoelsesince "):
            whoelsesince(conn_socket, user, username, inbound)
        elif inbound.startswith("block "):
            block(conn_socket, user, inbound)
        elif inbound.startswith("unblock "):
            unblock(conn_socket, user, inbound)
        elif inbound.startswith("startprivate "):
            startprivate(conn_socket, user, username, inbound)
        elif inbound.startswith("respprivate "):
            respprivate(user, username, inbound)
        elif inbound == "private":
            user['last_online'] = curr_time()
        else:
            conn_socket.send(b"Error: Invalid command\n")
            # Set the timeout as if the command wasn't received
            conn_socket.settimeout(timeout - (curr_time() - user['last_online']))

        # Refresh at 20Hz
        sleep(0.05)

def flush_messages(conn_socket, user):
    try:
        buffer = user['message_buffer']
        while user['online']:
            try:
                buffer[0]
                conn_socket.send(buffer[0].encode())
                conn_socket.send(b"\n")
            except IndexError:
                pass
            else:
                buffer.pop(0)
            # Refresh at 20Hz
            sleep(0.05)

    except KeyboardInterrupt:
        pass

def authenticate(conn_socket):
    # Obtain username
    conn_socket.send(b"Username: ")
    username = conn_socket.recv(1024).decode()
    un_len = len(username)

    # Search for username and password in credentials
    password = None
    with open("credentials.txt", 'a+') as f:
        f.seek(0)
        for line in f:
            line = line.split(' ', 1)
            if len(line) >= 2 and line[0] == username:
                password = line[1][0:-1]
                break

    # If the user is new, set their password and create their user dictionary
    if password is None:
        conn_socket.send(b"This is a new user. Enter a password: ")
        password = conn_socket.recv(1024).decode()

        if password == "":
            raise Exception(f"{username} failed to register")
        with open("credentials.txt", 'a') as f:
            f.write(f"{username} {password}\n")

        user = users[username] = {
            'online': False,
            'last_online': None,
            'blocked_until': None,
            'blacklist': [],
            'message_buffer': [],
        }
        return (username, user)

    # Check for the user already being logged in or blocked
    user = users.get(username)
    if user is not None:
        if user['online']:
            conn_socket.send(b"Your account is already logged in on another client.\n")
            raise Exception(f"{username} is already online")

        if user['blocked_until'] and user['blocked_until'] > curr_time():
            conn_socket.send(
            b"Your account is blocked due to multiple login failures. Please try again later\n")
            raise Exception(f"{username} is blocked for multiple login failures")

        user['blocked_until'] = None
    else:
        user = users[username] = {
            'online': False,
            'last_online': None,
            'blocked_until': None,
            'blacklist': [],
            'message_buffer': [],
        }

    # Attempt to authenticate the user with their password
    conn_socket.send(b"Password: ")
    attempts = 0
    while True:
        entered_pass = conn_socket.recv(1024).decode()
        if entered_pass == password:
            return (username, user)

        attempts += 1
        if attempts >= 3:
            break

        conn_socket.send(b"Invalid Password. Please try again\nPassword: ")

    conn_socket.send(b"Invalid Password. Your account has been blocked. Please try again later\n")

    user['blocked_until'] = curr_time() + block_duration
    raise Exception(f"{username} failed to authenticate themselves")

def presence_broadcast(username, message):

    print(message)
    for user in users.values():
        if user['online'] and username not in user['blacklist']:
            user['message_buffer'].append(message)

def message_user(conn_socket, sender, sender_name, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 2)
    if len(args) < 3:
        conn_socket.send(b"Usage: message <user> <message>\n")
        return
    recipient = users.get(args[1]); message = args[2]

    # The recipient must exist as a user, and not be the sender or have the sender blocked
    if recipient is None:
        conn_socket.send(b"Error: Invalid user\n")
    elif recipient is sender:
        conn_socket.send(b"Error: Cannot message self\n")
    elif sender_name in recipient['blacklist']:
        conn_socket.send(f"Error: {args[1]} has blocked you\n".encode())
    else:
        recipient['message_buffer'].append(f"{sender_name}: {message}")

def broadcast(conn_socket, sender, sender_name, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 1)
    if len(args) < 2:
        conn_socket.send(b"Usage: broadcast <message>\n")
        sender['last_online'] = curr_time()
        return
    message = args[1]

    blacklisted = False
    for user in users.values():
        if user is not sender:
            if sender_name in user['blacklist']:
                blacklisted = True
            else:
                user['message_buffer'].append(f"{sender_name}: {message}")

    if blacklisted:
        conn_socket.send(b"Your broadcast was not received by users who have blocked you.\n")

def whoelse(conn_socket, sender, sender_name):

    sender['last_online'] = curr_time()

    for username, user in users.items():
        if user['online'] and not (user is sender or sender_name in user['blacklist']):
            conn_socket.send(f"{username}\n".encode())

def whoelsesince(conn_socket, sender, sender_name, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 1)
    if len(args) < 2:
        conn_socket.send(b"Usage: whoelsesince <time>\n")
        return
    try:
        time_int = int(args[1])
    except:
        conn_socket.send(b"Error: Time entered must be a decimal integer\n")
        return
    target_time = curr_time() - time_int

    for username, user in users.items():
        if not (user is sender or sender_name in user['blacklist']):
            last_online = user['last_online']
            # Checking for None is necessary
            if last_online and last_online >= target_time:
                conn_socket.send(f"{username}\n".encode())

def block(conn_socket, sender, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 1)
    if len(args) < 2:
        conn_socket.send(b"Usage: block <user>\n")
        return
    username = args[1]
    user = users.get(username)

    if user is None:
        conn_socket.send(b"Error: Invalid user\n")
    elif user is sender:
        conn_socket.send(b"Error: Cannot block self\n")
    elif username in sender['blacklist']:
        conn_socket.send(f"Error: {username} was already blocked\n".encode())
    else:
        sender['blacklist'].append(username)
        conn_socket.send(f"Successfully blocked {username}\n".encode())

def unblock(conn_socket, sender, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 1)
    if len(args) < 2:
        conn_socket.send(b"Usage: unblock <user>\n")
        return
    username = args[1]
    user = users.get(username)

    if user is None:
        conn_socket.send(b"Error: Invalid user\n")
    elif user is sender:
        conn_socket.send(b"Error: Cannot unblock self\n")
    else:
        try:
            sender['blacklist'].remove(username)
        except ValueError:
            conn_socket.send(f"Error: {username} was not blocked\n".encode())
        else:
            conn_socket.send(f"Successfully unblocked {username}\n".encode())

def startprivate(conn_socket, sender, sender_name, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 1)
    if len(args) < 2:
        conn_socket.send(b"Usage: startprivate <user>\n")
        return
    username = args[1]
    user = users.get(username)

    if user is None:
        conn_socket.send(b"Error: Invalid user\n")
    elif user is sender:
        conn_socket.send(b"Error: Cannot private chat with self\n")
    elif sender_name in user['blacklist']:
        conn_socket.send(f"Error: {username} has blocked you\n".encode())
    elif not user['online']:
        conn_socket.send(f"Error: {username} is offline\n".encode())
    else:
        user['message_buffer'].append(f"reqprivate {sender_name}")
        conn_socket.send(f"Sent a private messaging request to {username}\n".encode())

def respprivate(sender, sender_name, inbound):

    sender['last_online'] = curr_time()

    args = inbound.split(' ', 2)
    if len(args) < 3:
        # Don't send anything; this is a 'hidden' command
        return
    user = users.get(args[1])
    port = args[2]

    if user is None:
        return
    if port == "None":
        user['message_buffer'].append(f"{sender_name} has declined the request")
    else:
        user['message_buffer'].append(f"initprivate {sender_name} {port}")

if __name__ == "__main__":
    main()
