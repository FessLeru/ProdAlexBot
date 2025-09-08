"""Главный файл для запуска всех систем."""
import asyncio
import logging

from config.constants import COINS, LEVERAGE
from config.settings import settings
from database.connection import db
from trading.celery_worker import start_master_trading
from telegram.bot import start_bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_database() -> None:
    """Инициализация базы данных."""
    logger.info("🚀 Инициализация системы")
    await db.init_db()
    logger.info("✅ База данных готова")


def start_trading() -> None:
    """Запуск торговых задач через Celery."""
    logger.info("🎯 Запуск торговых задач")
    
    # Рассчитываем депозит на монету (примерный расчет)
    deposit_per_coin = 20  # USDT на каждую монету
    
    start_master_trading.delay(
        api_key=settings.TRADER_API_KEY,
        api_secret=settings.TRADER_API_SECRET,
        api_passphrase=settings.TRADER_API_PASSPHRASE,
        deposit_per_coin=deposit_per_coin
    )
    
    logger.info(f"✅ Запущено {len(COINS)} торговых монет")


async def main() -> None:
    """Главная функция."""
    try:
        # Инициализация БД
        await init_database()
        
        # Запуск торговли
        start_trading()
        
        # Запуск бота (блокирующий)
        await start_bot()
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал завершения")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())