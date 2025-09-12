"""Модуль для работы с Redis кэшем торговой системы."""
import redis.asyncio as redis
import logging
from typing import List

from config.settings import settings

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Менеджер для работы с Redis кэшем."""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.cache_patterns: List[str] = [
            "active_orders:*",      # Кэш активных ордеров
            "order_status:*",       # Кэш статусов ордеров  
            "filled_summary:*",     # Кэш сводок исполненных ордеров
            "take_profit:*"         # Кэш тейк-профит ордеров
        ]
    
    async def clear_all_cache(self) -> None:
        """
        Очистка всего кэша торговой системы.
        
        Удаляет все ключи кэша, используемые в торговой системе.
        """
        try:
            logger.info("🧹 Начинаем очистку Redis кэша")
            
            total_deleted = 0
            
            for pattern in self.cache_patterns:
                try:
                    keys = await self.redis_client.keys(pattern)
                    
                    if keys:
                        deleted_count = await self.redis_client.delete(*keys)
                        total_deleted += deleted_count
                        logger.info(f"🗑️ Удалено {deleted_count} ключей по паттерну '{pattern}'")
                    else:
                        logger.info(f"ℹ️ Ключи по паттерну '{pattern}' не найдены")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка при удалении ключей по паттерну '{pattern}': {e}")
            
            if total_deleted > 0:
                logger.info(f"✅ Очистка Redis завершена: удалено {total_deleted} ключей кэша")
            else:
                logger.info("ℹ️ Redis кэш уже был пуст")
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при очистке Redis: {e}")
    
    async def close(self) -> None:
        """Закрытие соединения с Redis."""
        await self.redis_client.close()


# Глобальный экземпляр менеджера кэша
cache_manager = RedisCacheManager()
