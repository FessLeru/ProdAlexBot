"""Обработчики для ввода API ключей."""
import logging

from telebot.types import Message

from config.settings import settings
from database.connection import db
from database.repositories.user_repo import UserRepository
from trading.models import UserStatus
from utils.encryption import encrypt_data
from telegram.bot_instance import bot
from telegram.states import (
    state_storage, 
    API_KEY_STATE, 
    API_SECRET_STATE, 
    API_PASSPHRASE_STATE
)

logger = logging.getLogger(__name__)


async def is_api_key_state(message: Message) -> bool:
    """Проверка состояния API ключа."""
    current_state = await state_storage.get_state(message.from_user.id, message.chat.id)
    return current_state == API_KEY_STATE


async def is_api_secret_state(message: Message) -> bool:
    """Проверка состояния API секрета."""
    current_state = await state_storage.get_state(message.from_user.id, message.chat.id)
    return current_state == API_SECRET_STATE


async def is_api_passphrase_state(message: Message) -> bool:
    """Проверка состояния API фразы."""
    current_state = await state_storage.get_state(message.from_user.id, message.chat.id)
    return current_state == API_PASSPHRASE_STATE


@bot.message_handler(func=is_api_key_state)
async def api_key_handler(message: Message) -> None:
    """Обработчик ввода API ключа."""
    await state_storage.set_data(
        message.from_user.id, 
        message.chat.id, 
        {"api_key": message.text.strip()}
    )
    await state_storage.set_state(message.from_user.id, message.chat.id, API_SECRET_STATE)
    await bot.send_message(
        message.chat.id,
        "Отправьте ваш API Secret:",
        parse_mode="HTML"
    )


@bot.message_handler(func=is_api_secret_state)
async def api_secret_handler(message: Message) -> None:
    """Обработчик ввода API секрета."""
    data = await state_storage.get_data(message.from_user.id, message.chat.id) or {}
    data["api_secret"] = message.text.strip()
    await state_storage.set_data(message.from_user.id, message.chat.id, data)
    await state_storage.set_state(message.from_user.id, message.chat.id, API_PASSPHRASE_STATE)
    await bot.send_message(
        message.chat.id,
        "Отправьте вашу API Passphrase:",
        parse_mode="HTML"
    )


@bot.message_handler(func=is_api_passphrase_state)
async def api_passphrase_handler(message: Message) -> None:
    """Обработчик ввода API фразы и сохранение ключей."""
    data = await state_storage.get_data(message.from_user.id, message.chat.id) or {}
    api_key = data.get("api_key")
    api_secret = data.get("api_secret")
    api_passphrase = message.text.strip()

    try:
        # Шифруем ключи
        encrypted_key = encrypt_data(api_key)
        encrypted_secret = encrypt_data(api_secret)
        encrypted_passphrase = encrypt_data(api_passphrase)

        # Сохраняем в БД
        user_repo = UserRepository(db)
        await user_repo.update_api_keys(
            user_id=message.from_user.id,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            api_passphrase_encrypted=encrypted_passphrase
        )

        await user_repo.update_user_status(
            user_id=message.from_user.id,
            status=UserStatus.ACTIVE,
            is_following=True
        )

        await bot.send_message(
            message.chat.id,
            "✅ API ключи успешно сохранены!\n\n"
            "Теперь вы участвуете в копи-трейдинге.",
            parse_mode="HTML"
        )
        
        # Уведомляем админа
        await _notify_admin(f"🆕 Новый пользователь: @{message.from_user.username}")

    except Exception as e:
        logger.error(f"Ошибка сохранения API ключей: {e}")
        await bot.send_message(
            message.chat.id,
            "❌ Ошибка сохранения ключей. Попробуйте снова."
        )

    await state_storage.delete_state(message.from_user.id, message.chat.id)


async def _notify_admin(text: str) -> None:
    """Уведомление администратора."""
    try:
        for admin_id in settings.ADMIN_TELEGRAM_IDS:
            await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")
