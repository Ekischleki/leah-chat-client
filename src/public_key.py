#Due to circular imports, we sadly can't import crypto
from cryptography.hazmat.primitives import serialization
import hashlib


import base64
class PublicKey:
    def __init__(self, inner):
        self.inner = inner
    def key_bytes(self) -> bytes:
        return self.inner.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    def as_base64_string(self) -> str:
        key_bytes = self.key_bytes()
        return base64.b64encode(key_bytes).decode("utf-8")
    
    def __eq__(self, value):
        if value is None or self is None:
            return False
        return self.as_base64_string() == value.as_base64_string() 
    

    def fingerprint(self):
        m = hashlib.sha256()
        m.update(self.key_bytes())
        return m.digest()

    def __hash__(self):
        return self.as_base64_string().__hash__()

    
def from_rsa(rsa) -> PublicKey:
    return PublicKey(rsa)

def from_base64_string(str: str) -> PublicKey:
    public_key_bytes = base64.b64decode(str)
    public_key = serialization.load_der_public_key(public_key_bytes)
    return PublicKey(public_key)