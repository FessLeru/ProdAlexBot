"""Инлайн клавиатуры."""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создает основную клавиатуру.
    
    Returns:
        InlineKeyboardMarkup: Основная клавиатура.
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats")
    )
    return keyboard
