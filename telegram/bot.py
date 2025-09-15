import asyncio
import logging
from typing import Optional

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from config.settings import settings
from telegram.bot_instance import bot
from telegram.handlers import *  # Импортируем все обработчики для их регистрации

logger = logging.getLogger(__name__)


async def start_kafka_consumer() -> None:
    """Запускает Kafka потребителя для уведомлений."""
    consumer: Optional[AIOKafkaConsumer] = None
    
    try:
        consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_NOTIFICATIONS,
            bootstrap_servers=settings.KAFKA_SERVERS,
            group_id='telegram_bot',
            auto_offset_reset='latest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000
        )
        
        await consumer.start()
        logger.info("✅ Kafka потребитель успешно запущен")
        
        async for message in consumer:
            try:
                notification = message.value.decode('utf-8')
                await _notify_admin(notification)
                logger.debug(f"Обработано Kafka сообщение: {notification[:50]}...")
            except UnicodeDecodeError as e:
                logger.error(f"Ошибка декодирования Kafka сообщения: {e}")
            except Exception as e:
                logger.error(f"Ошибка обработки Kafka сообщения: {e}")
                
    except KafkaError as e:
        logger.error(f"Ошибка Kafka подключения: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка Kafka потребителя: {e}")


async def _notify_admin(text: str) -> None:
    """Уведомляет администраторов."""
    try:
        for admin_id in settings.ADMIN_TELEGRAM_IDS:
            try:
                await bot.send_message(admin_id, text)
                logger.debug(f"Уведомление отправлено администратору {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Общая ошибка уведомления администраторов: {e}")


async def start_bot() -> None:
    """Запускает бота с Kafka потребителем."""
    logger.info("🤖 Запуск Telegram бота")
    
    # Запускаем Kafka потребитель и бота одновременно
    await asyncio.gather(
        start_kafka_consumer(),
        bot.polling()
    )
