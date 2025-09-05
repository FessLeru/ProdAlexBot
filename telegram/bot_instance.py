"""Экземпляр Telegram бота."""
from telebot.async_telebot import AsyncTeleBot

from config.settings import settings
from telegram.states import state_storage

bot = AsyncTeleBot(settings.BOT_TOKEN, state_storage=state_storage)
