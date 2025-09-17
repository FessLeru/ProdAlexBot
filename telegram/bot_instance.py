"""Экземпляр Telegram бота."""
from telebot.async_telebot import AsyncTeleBot
from telebot import asyncio_filters

from config.settings import settings
from telegram.states import state_storage

bot = AsyncTeleBot(settings.BOT_TOKEN, state_storage=state_storage)
bot.add_custom_filter(asyncio_filters.StateFilter(bot))
