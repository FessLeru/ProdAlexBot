"""Генератор ключа шифрования."""

from cryptography.fernet import Fernet


def generate_key() -> str:
    """
    Генерирует ключ шифрования Fernet.
    
    Returns:
        str: Base64-кодированный ключ шифрования.
    """
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    key: str = generate_key()
    print(f"ENCRYPTION_KEY={key}")
