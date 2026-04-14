from base64 import b64decode, b64encode
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

from config import Config

config = Config()

aes_key = config.kodeliste.aes_key.encode("ascii")

def decrypt(iv_cipher: str) -> str:
    """Decrypt a given string using internal format.
        Uses an AES key in memory; PKCS7 format

    Args:
        iv_cipher (str): Cipher on format iv:cipher

    Raises:
        ValueError: Encrypted string must be in format iv:cipher
        ValueError: AES key is missing, cannot decrypt

    Returns:
        str: UTF8-decoded string
    """
     
    parts = iv_cipher.split(":")

    if len(parts) != 2:
        raise ValueError("Encrypted string must be in format iv:cipher")

    if not aes_key:
        raise ValueError("AES key is missing, cannot decrypt")

    iv = b64decode(parts[0])
    cipher_text = b64decode(parts[1])

    cipher = Cipher(
        algorithms.AES(aes_key),
        modes.CBC(iv),
        backend=default_backend()
    )

    decryptor = cipher.decryptor()
    padded_plain = decryptor.update(cipher_text) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded_plain) + unpadder.finalize()

    return plain.decode("utf-8")

def encrypt(plaintext: str) -> str:
    """Encrypt a given string using internal format.
        Uses an AES key in memory; PKCS7 format

    Args:
        plaintext (str): Plaintext to be encrypted

    Raises:
        ValueError: AES key is missing, cannot encrypt

    Returns:
        str: Base64-encoded iv:cipher
    """
    if not aes_key:
        raise ValueError("AES key is missing, cannot encrypt")

    iv = os.urandom(16)

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    iv_b64 = b64encode(iv).decode()
    cipher_b64 = b64encode(ciphertext).decode()

    return f"{iv_b64}:{cipher_b64}"
