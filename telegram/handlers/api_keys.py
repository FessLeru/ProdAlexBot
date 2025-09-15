"""Обработчики для ввода API ключей."""
import logging

from telebot.types import Message

from config.settings import settings
from database.connection import db
from database.repositories.user_repo import UserRepository
from trading.models import UserStatus
from utils.encryption import encrypt_data
from telegram.bot_instance import bot
from telegram.states import state_storage, MyStates

logger = logging.getLogger(__name__)


@bot.message_handler(state=MyStates.api_key)
async def api_key_handler(message: Message, state) -> None:
    """Обработчик ввода API ключа."""
    state.set(MyStates.api_secret)
    state.add_data(api_key=message.text.strip())
    await bot.send_message(
        message.chat.id,
        "Отправьте ваш API Secret:",
        parse_mode="HTML"
    )


@bot.message_handler(state=MyStates.api_secret)
async def api_secret_handler(message: Message, state) -> None:
    """Обработчик ввода API секрета."""
    state.set(MyStates.api_passphrase)
    state.add_data(api_secret=message.text.strip())
    await bot.send_message(
        message.chat.id,
        "Отправьте вашу API Passphrase:",
        parse_mode="HTML"
    )


@bot.message_handler(state=MyStates.api_passphrase)
async def api_passphrase_handler(message: Message, state) -> None:
    """Обработчик ввода API фразы и сохранение ключей."""
    data = state.get_data()
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

    state.delete_state()


async def _notify_admin(text: str) -> None:
    """Уведомление администратора."""
    try:
        for admin_id in settings.ADMIN_TELEGRAM_IDS:
            try:
                await bot.send_message(admin_id, text)
                logger.debug(f"Уведомление отправлено администратору {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Общая ошибка уведомления администраторов: {e}")
