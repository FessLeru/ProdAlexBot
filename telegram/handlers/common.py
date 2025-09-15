"""Общие обработчики команд."""
import logging

from telebot.types import Message

from database.connection import db
from database.repositories.user_repo import UserRepository
from trading.models import UserModel, UserStatus
from telegram.bot_instance import bot
from telegram.states import state_storage, MyStates

logger = logging.getLogger(__name__)


@bot.message_handler(commands=['start'])
async def start_handler(message: Message) -> None:
    """Обработчик команды /start."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    
    if not user:
        # Создаем нового пользователя
        user_model = UserModel(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            status=UserStatus.PENDING
        )
        await user_repo.create(user_model)
        
    text = (
        "🤖 Добро пожаловать в торгового бота Bybit!\n\n"
        "📋 Доступные команды:\n"
        "/keys - Добавить API ключи Bybit\n\n"
        "⚠️ Убедитесь, что API ключи имеют права на торговлю фьючерсами."
    )
    
    await bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=['keys'])
async def keys_handler(message: Message) -> None:
    """Обработчик команды /keys."""
    await state_storage.set_state(message.from_user.id, message.chat.id, MyStates.api_key)
    await bot.send_message(
        message.chat.id,
        "🔐 Добавление API ключей Bybit\n\n"
        "Отправьте ваш API Key:",
        parse_mode="HTML"
    )
