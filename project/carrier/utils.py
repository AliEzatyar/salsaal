from django.conf import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
from Crypto.Util.Padding import pad, unpad


SECRET = settings.DUMMY_SECRET.encode("utf-8")  # must be 16, 24, or 32 bytes
IV = bytes([0] * 16)  # AES block size = 16

print("this is secret", SECRET)


def get_carrier_key(id):
    return f"carrier:{id}:live"


def encrypt_32(order_id: str) -> str:
    order_id = str(order_id)
    cipher = AES.new(SECRET, AES.MODE_CBC, IV)
    encrypted_bytes = cipher.encrypt(pad(order_id.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def decrypt_32(text):
    text = str(text).strip()
    # try:
    # Decode from Base64 (Flutter/JS sends Base64)
    encrypted_bytes = base64.b64decode(text)

    # Create AES cipher
    cipher = AES.new(SECRET, AES.MODE_CBC, IV)

    # Decrypt & unpad
    decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)

    returnee = decrypted_bytes.decode("utf-8")
    print("decrypted", returnee)
    return returnee
    # except Exception as e:
    #     print("error in decrypt", e)
    #     return None
