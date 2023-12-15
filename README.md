# PySockChat
A CLI chat application using sockets between a local server and its clients, written in Python.

## Structure
This application consists of two files, `server.py` and `client.py`. Based on the client-server model, multiple clients may exist, but only one server may operate at a time.

The server exists for clients to interact with each other. Clients exist for users to interact with the application.

## Running the Application
This application requires Python3 to be installed.

### Server
To start the server, run `python3 server.py [server_port] [block_duration] [timeout]`, where each argument is an integer without any brackets.

`server_port` is the port number which the server will use to communicate with its clients.

`block_duration` is the number of seconds for which a user will be blocked after failing to authenticate themselves three times in a row.

`timeout` is the number of seconds of inactivity after which a user will be logged off the server.

### Client
To start a client, run `python3 client.py [server_port]`.

Upon connecting, the client must authenticate its user, by providing their username and password. (Note that authentication data is persistent.)
Upon successful authentication, all online users will be notified that this client's user has logged in. (This excludes other users who have blocked this user.)

### Client Commands
A client may run the following commands:

`message [user] [message]` sends the user the message, if not blocked. If the user is offline, they will receive the message the next time they log in.

`broadcast [message]` sends all online users the message, except those who have blocked the user.

`whoelse` lists all other online users, except those who have blocked the user.

`whoelsesince [time]` lists all other users who have logged in in the past `[time]` seconds, except those who have blocked the user.

`block [user]` blocks the user, and prevents them from sending messages to the client's user, or knowing when they are online or have logged in.

`unblock [user]` unblocks the user.

`logout` logs the client's user out.

Both the server and client may be terminated at any time by triggering a `KeyboardInterrupt`. Terminating a server will also terminate all of its connected clients. Terminating a client is equivalent to using the `logout` command.

### Private Chats
There are also a few commands a client may use to initiate a private chat with the user of another client, that bypasses the server (with a p2p connection):

`startprivate [user]` sends a request for a private chat to the user. If they accept the request, the private chat will be initiated. It will terminate as soon as any of the two users logout.

`private [user] [message]` sends the private message to the user, if a private chat with the user exists.

`stopprivate [user]` terminates the private chat with the user.
