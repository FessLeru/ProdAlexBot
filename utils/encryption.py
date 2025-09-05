"""Утилиты для шифрования и расшифрования данных."""
from typing import Optional

from cryptography.fernet import Fernet

from config.settings import settings


def encrypt_data(data: str) -> str:
    """
    Шифрует строку данных.
    
    Args:
        data (str): Данные для шифрования.
        
    Returns:
        str: Зашифрованные данные в формате строки.
    """
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    return cipher.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> Optional[str]:
    """
    Расшифровывает зашифрованные данные.
    
    Args:
        encrypted_data (str): Зашифрованные данные.
        
    Returns:
        Optional[str]: Расшифрованные данные или None при ошибке.
    """
    try:
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        return cipher.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return None
