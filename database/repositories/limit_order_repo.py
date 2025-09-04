import aiosqlite
import redis.asyncio as redis
import json
import logging
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import datetime

from database.connection import db
from config.settings import settings

logger = logging.getLogger(__name__)

class LimitOrderRepository:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.cache_ttl = 3600  # 1 час
    
    async def get_orders_ids(self, symbol: str) -> List[str]:
        """Получение ID лимитных ордеров с кэшированием"""
        cache_key = f"limit_orders:{symbol}"
        
        # Пытаемся получить из кэша
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # Если нет в кэше - запрос к БД
        query = """
            SELECT order_id FROM limit_orders 
            WHERE symbol = ? AND status IN ('pending', 'partial_filled')
            ORDER BY grid_level ASC
        """
        
        rows = await db.execute_query(query, (symbol,))
        order_ids = [row['order_id'] for row in rows]
        
        # Кэшируем результат
        await self.redis_client.setex(
            cache_key, 
            self.cache_ttl, 
            json.dumps(order_ids)
        )
        
        return order_ids
    
    async def get_order_status(self, order_id: str) -> Optional[str]:
        """Получение статуса ордера из кэша или БД"""
        cache_key = f"order_status:{order_id}"
        
        # Проверяем кэш
        status = await self.redis_client.get(cache_key)
        if status:
            return status
        
        # Запрос к БД
        query = "SELECT status FROM limit_orders WHERE order_id = ?"
        row = await db.execute_single(query, (order_id,))
        
        if row:
            status = row['status']
            # Кэшируем на короткое время
            await self.redis_client.setex(cache_key, 60, status)
            return status
        
        return None
    
    async def update_order_status(self, order_id: str, status: str, filled_quantity: Decimal = None):
        """Обновление статуса ордера с инвалидацией кэша"""
        if filled_quantity is not None:
            query = """
                UPDATE limit_orders 
                SET status = ?, filled_quantity = ?, filled_at = ?
                WHERE order_id = ?
            """
            params = (status, float(filled_quantity), datetime.utcnow().isoformat(), order_id)
        else:
            query = "UPDATE limit_orders SET status = ? WHERE order_id = ?"
            params = (status, order_id)
        
        await db.execute_write(query, params)
        
        # Инвалидируем кэш
        await self._invalidate_order_cache(order_id)
    
    async def get_filled_orders_for_symbol(self, symbol: str) -> List[Dict]:
        """Получение исполненных ордеров для расчета средней цены"""
        query = """
            SELECT order_id, price, filled_quantity, grid_level
            FROM limit_orders 
            WHERE symbol = ? AND status = 'filled'
            ORDER BY grid_level ASC
        """
        
        rows = await db.execute_query(query, (symbol,))
        return [
            {
                'order_id': row['order_id'],
                'price': Decimal(str(row['price'])),
                'quantity': Decimal(str(row['filled_quantity'])),
                'grid_level': row['grid_level']
            }
            for row in rows
        ]
    
    async def batch_update_filled_orders(self, updates: List[tuple]):
        """Батчевое обновление исполненных ордеров"""
        if not updates:
            return
            
        query = """
            UPDATE limit_orders 
            SET status = ?, filled_quantity = ?, filled_at = ?
            WHERE order_id = ?
        """
        
        await db.execute_many(query, updates)
        
        # Инвалидируем кэш для всех обновленных ордеров
        for update in updates:
            order_id = update[3]  # order_id последний в tuple
            await self._invalidate_order_cache(order_id)
    
    async def save_order(self, order) -> bool:
        """Сохранение нового ордера в БД"""
        try:
            query = """
                INSERT INTO limit_orders (symbol, order_id, price, quantity, status, grid_level, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                order.symbol,
                order.order_id,
                float(order.price),
                float(order.quantity), 
                order.status.value,
                order.grid_level,
                order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat()
            )
            
            await db.execute_write(query, params)
            
            # Инвалидируем кэш
            await self._invalidate_order_cache(order.order_id)
            
            logger.info(f"✅ Сохранен ордер {order.order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения ордера {order.order_id}: {e}")
            return False
    
    async def _invalidate_order_cache(self, order_id: str):
        """Инвалидация кэша для ордера"""
        # Получаем символ ордера для очистки кэша списка ордеров
        query = "SELECT symbol FROM limit_orders WHERE order_id = ?"
        row = await db.execute_single(query, (order_id,))
        
        if row:
            symbol = row['symbol']
            # Удаляем из кэша
            await self.redis_client.delete(f"limit_orders:{symbol}")
            await self.redis_client.delete(f"order_status:{order_id}")
