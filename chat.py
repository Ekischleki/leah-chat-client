#Interface for the cli

import sys
from src import chat_app
from src import user_config
from src import client_state
from src import client_poller
import time

def msg_received(self, message, sender):
    pass

def print_chats(client: client_state.ClientState):
    if len(client.chats) == 0:
        print("<No chats>")
        return
    for chat in client.chats.keys():
        chat_name = client.get_key_name(chat)
        print(f"Chat: {chat_name}")
        chat_state = client.chats[chat]
        if len(chat_state.messages) == 0:
            print("\t<No messages yet>")
            continue
        last_message = chat_state.messages[-1]
        if last_message.sent_by_client:
            last_message_sender = "You"
        else:
            last_message_sender = chat_name
        last_message_text = last_message.message
        if len(last_message_text) > 103:
            last_message_text = last_message_text[0:100] + "..."
        print(f"\t{last_message_sender}: {last_message_text}")

def search_clients(client: client_state.ClientState):
    for _ in range(70):
        client_poller.update(client)
        time.sleep(1)

args = sys.argv

if "-r" in args:
    print("Are you sure you want to delete the client save data (this will not affect your public keys) y/N")
    print("Just kidding, we haven't implemented checking for y/N yet.")
    user_config.write_config({})

print("---- Starting client ----")
username = chat_app.load_or_create_username()
client = chat_app.load_or_new_client(username, lambda: ())

print("----- Client Loaded -----")
i = 0

while i < len(args):
    arg = args[i]
    remain = len(args) - i - 1
    match arg:
        case "--ui":
            import main_client #yup
        case "-h":
            print("*Insert helpful help text*")
        case "-l" | "--list":
            print_chats(client)
        case "--scan":
            print("-- Scanning for Clients --")
            search_clients(client)
        case _:
            print(f"Unknown option: {arg}")


    i += 1