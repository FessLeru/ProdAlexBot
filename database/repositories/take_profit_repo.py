import redis.asyncio as redis
import json
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from database.connection import db
from config.settings import settings
from trading.models import TakeProfitModel, OrderStatus

logger = logging.getLogger(__name__)

class TakeProfitRepository:
    """Репозиторий тейк-профит ордеров с быстрым кэшированием"""
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL, 
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.cache_ttl = 30  # Короткий TTL - тейк-профиты часто обновляются
    
    async def get_active_take_profit(self, symbol: str) -> Optional[TakeProfitModel]:
        """
        Получение активного тейк-профит ордера
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Optional[TakeProfitModel]: Модель тейк-профита или None
        """
        cache_key = f"take_profit:{symbol}"
        
        # Проверяем кэш
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            return TakeProfitModel(
                order_id=data['order_id'],
                symbol=symbol,
                price=Decimal(data['price']),
                quantity=Decimal(data['quantity']),
                status=OrderStatus(data['status']),
                created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
            )
        
        # Запрос к БД
        query = """
            SELECT order_id, price, quantity, status, created_at
            FROM take_profit_orders 
            WHERE symbol = ? AND status IN ('pending', 'partial_filled')
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        row = await db.execute_single(query, (symbol,))
        if not row:
            return None
        
        take_profit = TakeProfitModel(
            order_id=row['order_id'],
            symbol=symbol,
            price=Decimal(str(row['price'])),
            quantity=Decimal(str(row['quantity'])),
            status=OrderStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )
        
        # Кэшируем
        cache_data = {
            'order_id': take_profit.order_id,
            'price': str(take_profit.price),
            'quantity': str(take_profit.quantity),
            'status': take_profit.status.value,
            'created_at': take_profit.created_at.isoformat() if take_profit.created_at else None
        }
        
        await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(cache_data))
        
        return take_profit
    
    async def create_take_profit(self, symbol: str, order_id: str, price: Decimal, quantity: Decimal) -> bool:
        """
        Создание нового тейк-профит ордера (с отменой старого)
        
        Args:
            symbol: Торговый символ
            order_id: ID ордера
            price: Цена
            quantity: Количество
            
        Returns:
            bool: True если успешно создан
        """
        try:
            # Отменяем старые тейк-профиты
            await self._cancel_old_take_profits(symbol)
            
            # Создаем новый
            query = """
                INSERT INTO take_profit_orders (symbol, order_id, price, quantity, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """
            
            params = (symbol, order_id, float(price), float(quantity), datetime.utcnow().isoformat())
            await db.execute_write(query, params)
            
            # Инвалидируем кэш
            await self.redis_client.delete(f"take_profit:{symbol}")
            
            logger.info(f"✅ Создан тейк-профит {symbol}: {price} x {quantity}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания тейк-профита {symbol}: {e}")
            return False
    
    async def mark_filled(self, order_id: str) -> bool:
        """
        Отметка тейк-профита как исполненного
        
        Args:
            order_id: ID ордера
            
        Returns:
            bool: True если успешно обновлен
        """
        try:
            query = """
                UPDATE take_profit_orders 
                SET status = 'filled', filled_at = ?
                WHERE order_id = ?
            """
            
            await db.execute_write(query, (datetime.utcnow().isoformat(), order_id))
            
            # Получаем символ и инвалидируем кэш
            symbol_query = "SELECT symbol FROM take_profit_orders WHERE order_id = ?"
            row = await db.execute_single(symbol_query, (order_id,))
            if row:
                await self.redis_client.delete(f"take_profit:{row['symbol']}")
            
            logger.info(f"✅ Тейк-профит {order_id} отмечен как исполненный")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления тейк-профита {order_id}: {e}")
            return False
    
    async def _cancel_old_take_profits(self, symbol: str):
        """Отмена старых тейк-профит ордеров"""
        query = """
            UPDATE take_profit_orders 
            SET status = 'cancelled'
            WHERE symbol = ? AND status IN ('pending', 'partial_filled')
        """
        await db.execute_write(query, (symbol,))