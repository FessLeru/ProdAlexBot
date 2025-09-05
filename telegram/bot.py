import asyncio
import logging

from aiokafka import AIOKafkaConsumer

from config.settings import settings
from telegram.bot_instance import bot

logger = logging.getLogger(__name__)


async def start_kafka_consumer() -> None:
    """Запускает Kafka потребителя для уведомлений."""
    consumer = AIOKafkaConsumer(
        'trading_notifications',
        bootstrap_servers=settings.KAFKA_SERVERS,
        group_id='telegram_bot'
    )
    
    await consumer.start()
    logger.info("Kafka потребитель запущен")
    
    try:
        async for message in consumer:
            try:
                notification = message.value.decode('utf-8')
                await _notify_admin(notification)
            except Exception as e:
                logger.error(f"Ошибка обработки Kafka сообщения: {e}")
    except Exception as e:
        logger.error(f"Ошибка Kafka потребителя: {e}")
    finally:
        await consumer.stop()


async def _notify_admin(text: str) -> None:
    """Уведомляет администраторов."""
    try:
        for admin_id in settings.ADMIN_TELEGRAM_IDS:
            await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")


async def start_bot() -> None:
    """Запускает бота с Kafka потребителем."""
    logger.info("🤖 Запуск Telegram бота")
    
    # Запускаем Kafka потребитель в фоне
    kafka_task = asyncio.create_task(start_kafka_consumer())
    
    # Запускаем бота
    await bot.polling()
