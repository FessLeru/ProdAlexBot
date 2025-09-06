"""Запуск только торговых задач без бота."""
import asyncio
import logging

from config.constants import COINS
from config.settings import settings
from database.connection import db
from trading.celery_worker import start_master_trading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Запуск только торговли."""
    try:
        # Инициализация БД
        logger.info("🚀 Инициализация БД")
        await db.init_db()
        logger.info("✅ База данных готова")
        
        # Запуск торговли
        logger.info("🎯 Запуск торговых задач")
        deposit_per_coin = 100.0
        
        start_master_trading.delay(
            api_key=settings.TRADER_API_KEY,
            api_secret=settings.TRADER_API_SECRET,
            api_passphrase=settings.TRADER_API_PASSPHRASE,
            deposit_per_coin=deposit_per_coin
        )
        
        logger.info(f"✅ Запущено {len(COINS)} торговых монет")
        logger.info("🔄 Торговля запущена, можете закрыть этот процесс")
        
        # Держим процесс немного для завершения отправки задач
        await asyncio.sleep(5)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())


