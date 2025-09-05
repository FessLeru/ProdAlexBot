"""Состояния для Telegram бота."""
from telebot.asyncio_storage import StateMemoryStorage


# Создание хранилища состояний
state_storage = StateMemoryStorage()

# Состояния для ввода API ключей
API_KEY_STATE = "api_key"
API_SECRET_STATE = "api_secret"  
API_PASSPHRASE_STATE = "api_passphrase"
