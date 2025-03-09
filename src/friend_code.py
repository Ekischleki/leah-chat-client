import base64
from . import public_key
#Meant to replace visually similar characters in friend codes, so users have an easier time passing them around
original = "0O1Il"
replacement = "-+:!?"

t = str.maketrans(original, replacement)
t_inv = str.maketrans(replacement, original)


"""Parses the bytes into a friend code which is base64 encoded with a custom alphabet to account for ambiguous characters and adds a single hash character"""
def encode_unambiguous_base64(b: bytes) -> str:
    encoded = base64.b64encode(b).decode("utf-8")
    return encoded.translate(t)

def decode_unambiguous_base64(b: str) -> bytes:
    decoded = b.translate(t_inv)
    return base64.b64decode(decoded)

FRIEND_CODE_LENGTH = 16 #96 bits should be secure enough for now. Todo: Let users choose between 12, 16 and 20 character codes for tradeoff between security and comfort

def get_friend_code_bytes(pk: public_key.PublicKey) -> bytes:
    req_bytes = (FRIEND_CODE_LENGTH * 3) // 4 #6 bits make 1 char in base 64, so chars * 6 bits are needed which are chars * 6 / 8  = chars * 3 / 4 bytes
    return pk.fingerprint()[:req_bytes]

def get_friend_code(pk: public_key.PublicKey, display_to_user: bool) -> str:
    b = get_friend_code_bytes(pk)
    if display_to_user:
        return encode_unambiguous_base64(b)
    return base64.b64encode(b).decode("utf-8")

def is_matching_friend_key(pk: public_key.PublicKey, code: str) -> bool:
    return get_friend_code(pk) == code
