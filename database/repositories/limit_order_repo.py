import redis.asyncio as redis
import json
import logging
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import datetime

from database.connection import db
from config.settings import settings
from trading.models import OrderModel, OrderStatusUpdate

logger = logging.getLogger(__name__)

class LimitOrderRepository:
    """Репозиторий лимитных ордеров с агрессивным кэшированием"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL, 
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.cache_ttl = 60  # Короткий TTL для быстрых обновлений
        self.list_cache_ttl = 30  # Еще короче для списков ордеров
    
    async def get_active_orders_ids(self, symbol: str) -> List[str]:
        """
        Получение ID активных лимитных ордеров с кэшированием
        
        Args:
            symbol: Торговый символ
            
        Returns:
            List[str]: Список ID ордеров
        """
        cache_key = f"active_orders:{symbol}"
        
        # Пытаемся получить из кэша
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        
        # Запрос к БД
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
            self.list_cache_ttl, 
            json.dumps(order_ids)
        )
        
        return order_ids
    
    async def get_order_status_cached(self, order_id: str) -> Optional[str]:
        """
        Получение статуса ордера из кэша
        
        Args:
            order_id: ID ордера
            
        Returns:
            Optional[str]: Статус ордера или None
        """
        cache_key = f"order_status:{order_id}"
        return await self.redis_client.get(cache_key)
    
    async def batch_update_order_statuses(self, updates: List[OrderStatusUpdate]) -> bool:
        """
        Батчевое обновление статусов ордеров
        
        Args:
            updates: Список обновлений
            
        Returns:
            bool: True если успешно
        """
        if not updates:
            return True
            
        try:
            # Подготавливаем данные для БД
            db_updates = []
            cache_updates = {}
            symbols_to_invalidate = set()
            
            for update in updates:
                if update.filled_quantity is not None:
                    db_updates.append((
                        update.status.value,
                        float(update.filled_quantity),
                        update.filled_at.isoformat() if update.filled_at else datetime.utcnow().isoformat(),
                        update.order_id
                    ))
                else:
                    db_updates.append((
                        update.status.value,
                        update.order_id
                    ))
                
                # Подготавливаем кэш
                cache_updates[f"order_status:{update.order_id}"] = update.status.value
                
                # Получаем символ для инвалидации
                symbol_query = "SELECT symbol FROM limit_orders WHERE order_id = ?"
                row = await db.execute_single(symbol_query, (update.order_id,))
                if row:
                    symbols_to_invalidate.add(row['symbol'])
            
            # Обновляем БД
            if updates[0].filled_quantity is not None:
                query = """
                    UPDATE limit_orders 
                    SET status = ?, filled_quantity = ?, filled_at = ?
                    WHERE order_id = ?
                """
            else:
                query = "UPDATE limit_orders SET status = ? WHERE order_id = ?"
            
            await db.execute_many(query, db_updates)
            
            # Обновляем кэш статусов
            if cache_updates:
                pipe = self.redis_client.pipeline()
                for key, value in cache_updates.items():
                    pipe.setex(key, self.cache_ttl, value)
                await pipe.execute()
            
            # Инвалидируем кэш списков ордеров
            for symbol in symbols_to_invalidate:
                await self.redis_client.delete(f"active_orders:{symbol}")
            
            logger.info(f"✅ Обновлено {len(updates)} ордеров")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка батчевого обновления: {e}")
            return False
    
    async def get_filled_orders_summary(self, symbol: str) -> Dict:
        """
        Получение сводки по исполненным ордерам для расчета тейк-профита
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Dict: Сводка с общим количеством и средневзвешенной ценой
        """
        cache_key = f"filled_summary:{symbol}"
        
        # Проверяем кэш
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            return {
                'total_quantity': Decimal(data['total_quantity']),
                'weighted_price': Decimal(data['weighted_price']),
                'order_count': data['order_count']
            }
        
        # Запрос к БД
        query = """
            SELECT 
                SUM(filled_quantity) as total_quantity,
                SUM(price * filled_quantity) as total_value,
                COUNT(*) as order_count
            FROM limit_orders 
            WHERE symbol = ? AND status = 'filled' AND filled_quantity > 0
        """
        
        row = await db.execute_single(query, (symbol,))
        
        if not row or not row['total_quantity']:
            return {'total_quantity': Decimal('0'), 'weighted_price': Decimal('0'), 'order_count': 0}
        
        total_quantity = Decimal(str(row['total_quantity']))
        total_value = Decimal(str(row['total_value']))
        weighted_price = total_value / total_quantity if total_quantity > 0 else Decimal('0')
        
        result = {
            'total_quantity': total_quantity,
            'weighted_price': weighted_price,
            'order_count': row['order_count']
        }
        
        # Кэшируем на короткое время
        cache_data = {
            'total_quantity': str(result['total_quantity']),
            'weighted_price': str(result['weighted_price']),
            'order_count': result['order_count']
        }
        
        await self.redis_client.setex(cache_key, 30, json.dumps(cache_data))
        
        return result
    
    async def save_order(self, order: OrderModel) -> bool:
        """
        Сохранение нового ордера
        
        Args:
            order: Модель ордера
            
        Returns:
            bool: True если успешно сохранен
        """
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
            
            # Обновляем кэш
            await self.redis_client.setex(
                f"order_status:{order.order_id}", 
                self.cache_ttl, 
                order.status.value
            )
            
            # Инвалидируем кэш списка ордеров
            await self.redis_client.delete(f"active_orders:{order.symbol}")
            
            logger.info(f"✅ Сохранен ордер {order.order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения ордера {order.order_id}: {e}")
            return False