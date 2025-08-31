import asyncio
from celery import Celery
import logging

from config.settings import settings
from config.constants import COINS
from trading.order_tracker import OrderTracker

logger = logging.getLogger(__name__)

# Инициализация Celery
celery_app = Celery(
    'trading_bot',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

@celery_app.task(bind=True)
def start_trading_cycle(self, api_key: str, api_secret: str, api_passphrase: str):
    """Запуск торгового цикла"""
    logger.info("🚀 Запуск нового торгового цикла")
    
    # Ожидание 1 минута перед началом торговли
    logger.info("⏳ Ожидание 60 секунд перед началом торговли...")
    asyncio.sleep(60)
    
    # Создаем задачи для каждой монеты
    for coin in COINS:
        track_coin_orders.delay(coin, api_key, api_secret, api_passphrase)
        logger.info(f"📊 Запущено отслеживание для {coin}")
    
    logger.info("✅ Все задачи отслеживания запущены")

@celery_app.task(bind=True)
def track_coin_orders(self, symbol: str, api_key: str, api_secret: str, api_passphrase: str):
    """Отслеживание ордеров для конкретной монеты"""
    logger.info(f"🎯 Начинаем отслеживание ордеров для {symbol}")
    
    async def run_tracker():
        tracker = OrderTracker(api_key, api_secret, api_passphrase)
        await tracker.track_symbol(symbol)
    
    # Запускаем асинхронную функцию в новом event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_tracker())
    except Exception as e:
        logger.error(f"❌ Ошибка в задаче отслеживания {symbol}: {e}")
        raise
    finally:
        loop.close()
