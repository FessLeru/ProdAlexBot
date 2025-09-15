"""Состояния для Telegram бота."""
from telebot.asyncio_storage import StateMemoryStorage
from telebot.states import StatesGroup, State


# Создание хранилища состояний
state_storage = StateMemoryStorage()


class MyStates(StatesGroup):
    """Состояния для ввода API ключей."""
    api_key = State()
    api_secret = State()
