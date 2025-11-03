from django.conf import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
from Crypto.Util.Padding import pad, unpad
from os import urandom


SECRET = settings.DUMMY_SECRET.encode("utf-8")  # must be 16, 24, or 32 bytes


def get_carrier_key(id):
    """
    Generate a unique key for a carrier.

    Args:
        id: The ID of the carrier.

    Returns:
        A string representing the unique key for the carrier.
    """
    return f"carrier:{id}:live"


def encrypt_32(order_id: str) -> str:
    """
    Encrypt an order ID using AES encryption.

    Args:
        order_id: The order ID to encrypt.

    Returns:
        A Base64-encoded string containing the encrypted order ID and IV.
    """
    order_id = str(order_id)
    iv = urandom(16)  # Generate a random IV
    cipher = AES.new(SECRET, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(pad(order_id.encode("utf-8"), AES.block_size))
    return base64.b64encode(iv + encrypted_bytes).decode("utf-8")  # Prepend IV to encrypted data


def decrypt_32(text):
    """
    Decrypt an AES-encrypted order ID.

    Args:
        text: The Base64-encoded string containing the encrypted order ID and IV.

    Returns:
        The decrypted order ID as a string, or None if decryption fails.
    """
    text = str(text).strip()
    try:
        # Decode from Base64 (Flutter/JS sends Base64)
        encrypted_data = base64.b64decode(text)

        # Extract IV and encrypted bytes
        iv = encrypted_data[:16]
        encrypted_bytes = encrypted_data[16:]

        # Create AES cipher
        cipher = AES.new(SECRET, AES.MODE_CBC, iv)

        # Decrypt & unpad
        decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)

        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        return None  # Avoid exposing sensitive error details
