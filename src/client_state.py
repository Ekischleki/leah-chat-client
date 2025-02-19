from . import public_key
from . import signature
from . import crypto
from . import client_socket
from . import packet_creator
from . import user_config
import base64
import json
import copy

class Message:
    def __init__(self, message: str, sent_by_self: bool):
        self.message = message
        self.sent_by_client = sent_by_self
    def __json__(self):
        return {"message": self.message, "sent_by_client": self.sent_by_client}

def __message_from_json__(json: dict) -> Message:
        message = json["message"]
        sent_by_client = json["sent_by_client"]
        return Message(message, sent_by_client)

class ChatState:
    def __init__(self, symmetric_key: bytes, display_name: str, public_key: public_key.PublicKey, messages: list[Message] = None):
        self.symmetric_key = symmetric_key
        self.display_name = display_name
        self.public_key = public_key
        if messages:
            self.messages = messages
        else:
            self.messages = []

    def __json__(self):
        return {"encryption": "symmetric", "symmetric_key": base64.b64encode(self.symmetric_key).decode("utf-8"), "display_name": self.display_name, "public_key": self.public_key.as_base64_string(), "messages": [message.__json__() for message in self.messages]}



    def decrypt_verify_chat(self, message: bytes, decrypted_hash: bytes, nonce: bytes) -> str | None:
        decrypted_message = crypto.aes_decrypt(self.symmetric_key, nonce, message, None)
        if decrypted_message == None:
            return None
        received_hash = crypto.get_sha256_hash(decrypted_message)
        if received_hash == decrypted_hash:
            plain_message = decrypted_message.decode("utf-8")
            self.messages.append(Message(plain_message, False))
            return plain_message

def __state_from_json__(dict: dict) -> ChatState:
    encryption = dict["encryption"]
    if encryption != "symmetric":
        print("Error: No support for pre/post compromise encryption.")
        return
    symmetric_key = base64.b64decode(dict["symmetric_key"])
    display_name = dict["display_name"]
    pub_key = public_key.from_base64_string(dict["public_key"])
    messages = [__message_from_json__(message) for message in dict["messages"]]
    return ChatState(symmetric_key, display_name, pub_key, messages)


IP = '87.106.163.101'
PORT = 12345
        

class ClientState:

    def write_to_save(self):
        config = user_config.load_config()
        config["chats"] = [chat.__json__() for chat in self.chats.values()]
        user_config.write_config(config)

    def __init__(self, pub_key: public_key.PublicKey, priv_key, display_name: str, received_callback):
        self.chats: dict[public_key.PublicKey, ChatState] = dict()
        self.discovered_clients = dict()
        self.public_key = pub_key
        self.private_key = priv_key
        self.client_socket = client_socket.ClientSocket(IP, PORT)
        self.display_name = display_name
        self.msg_received_callback = received_callback
        self.message_queue = []

    
    def send_message(self, chat: public_key.PublicKey, message: str):
        chat_state = self.chats[chat]
        chat_state.messages.append(Message(message, True))
        message_bytes = message.encode("utf-8")
        hash = crypto.get_sha256_hash(message_bytes)
        (nonce, encrypted) = crypto.aes_encrypt(chat_state.symmetric_key, message_bytes, None)
        message_packet = packet_creator.create_direct_message(chat.as_base64_string(), encrypted, base64.b64encode(hash).decode("utf-8"), self.public_key.as_base64_string(), nonce)
        self.client_socket.send(message_packet)

    def query_name(self, name: str):
        wantsname_packet = packet_creator.create_wants_name_message(name)
        self.client_socket.send(wantsname_packet)

        
    
    def broadcast_self(self):
        signed_name = signature.sign_with(self.private_key, self.display_name.encode("utf-8"))
        exists_message = packet_creator.create_exists_message(self.public_key.as_base64_string(), self.display_name, signed_name.to_base64())
        self.client_socket.send(exists_message)

            

    def get_public_key(self) -> public_key.PublicKey:
        """Returns the global public key of this client"""
        return self.public_key
    
    def received_shared_secret(self, sender: public_key.PublicKey, encrypted_shared_secret: bytes, shared_secret_signature: signature.Signature):
        """The client has received a chat-initiating shared secret"""
        sym_key = crypto.rsa_decrypt(self.private_key, encrypted_shared_secret)
        if not shared_secret_signature.valid_for(sender, sym_key):
            return
        self.chats[sender] = ChatState(sym_key, self.get_key_name(sender), sender)
        self.message_queue.append(("Chat was instantiated", sender))          
        print("Received shared secret")
        pass

    def send_shared_secret(self, receiver: public_key.PublicKey):
        random_key = crypto.generate_aes_key()
        signed_key = signature.sign_with(self.private_key, random_key)
        encrypted_key = crypto.rsa_encrypt(receiver.inner, random_key)
        message_pckt = packet_creator.create_exchange_message(
            base64.b64encode(encrypted_key).decode("utf-8"),
            self.public_key.as_base64_string(),
            signed_key.to_base64(),
            receiver.as_base64_string()
        )
        self.client_socket.send(message_pckt)
        self.chats[receiver] = ChatState(random_key, self.get_key_name(receiver), receiver)            

    def get_key_name(self, key: public_key.PublicKey) -> str:
        formatted_key = key.as_base64_string()
        formatted_key = formatted_key[70:76] + "..." + formatted_key[-76:-70] # The first few bits of the public key are always the same, so we'll include some more random bits

        if not key in self.discovered_clients:
            username = "Unknown"
        else:
            username = self.discovered_clients[key]

        return username + " (" + formatted_key + ")"


    def received_message(self, sender: public_key.PublicKey, encrypted_message_bytes: bytes, decrypted_hash: bytes, nonce: bytes):
        """The client has received a message that is still encrypted.
        We need to check whether the decrypted message hash matches the decrypted hash, the other client might
        have been hacked otherwise :O
        
        Todo: We don't check yet whether the message has actually come from the pretended sender, enabeling people to send fake packets making this client think the other party has been hacked."""
        print("Received message")

        if not sender in self.chats:
            return #We dont know them, maybe log it?
        return_msg = self.chats[sender].decrypt_verify_chat(encrypted_message_bytes, decrypted_hash, nonce)
        
        if return_msg:
            #self.msg_recieved_callback(return_msg, sender)
            self.message_queue.append((return_msg, sender))          

    
    def received_healing(self, sender: public_key.PublicKey, encrypted_new_key: bytes, signature: signature.Signature):
        """The client received a healing message from the sender. 
        The encrypted_new_key has been asymetrically encrypted with the most current public key within the dm message context.
        """
        raise NotImplementedError()
        pass
    def other_wants(self, requested: str):
        """A client on the network requested that buffer servers send the most recent messages to the requested receiver.
        This function can be ignored by non-buffer clients"""
        #We'll implement it anyways and rebroadcast ourselves if the query matches our name
        if requested in self.display_name:
            self.broadcast_self()
    def other_wants_name(self, name_query: str):
        """A client on the network requested that buffer servers resend broadcast/exists messages of every user that matches a certain name query
        This function can be ignored by non-buffer clients"""
        pass
    def discovered_client(self, public_key: public_key.PublicKey, name: str, signature: signature.Signature):
        """Received a broadcast message where a connected client announces themselves. 
        Their name has been signed with the signature."""
        if not signature.valid_for(public_key, name.encode("utf-8")):
            print("Sig invalid " + public_key.as_base64_string() + "\nSig:" + signature.to_base64())
            return
        self.discovered_clients[public_key] = name
        print("Discovered: " + name)
        if public_key in self.chats:
            self.chats[public_key].display_name = name
    


def load_or_new_client(display_name: str, recieved_callback) -> ClientState:
    if not crypto.keys_exist():
        crypto.generate_rsa_key_pair()
    priv_key = crypto.load_private_key()
    pub_key = public_key.from_rsa(crypto.load_public_key())
    client = ClientState(pub_key, priv_key, display_name, recieved_callback)

    config = user_config.load_config()

    if "chats" in config:
        for chat in config["chats"]:
            chat_state = __state_from_json__(chat)
            client.chats[chat_state.public_key] = chat_state
            client.discovered_clients[chat_state.public_key] = chat_state.display_name

    return client