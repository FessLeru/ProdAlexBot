import aiosqlite
import redis.asyncio as redis
import json
import logging
from typing import Optional, Dict
from decimal import Decimal
from datetime import datetime

from database.connection import db
from config.settings import settings

logger = logging.getLogger(__name__)

class TakeProfitRepository:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.cache_ttl = 300  # 5 минут (тейк-профит часто меняется)
    
    async def get_take_profit(self, symbol: str) -> Optional[Dict]:
        """Получение тейк-профит ордера с кэшированием"""
        cache_key = f"take_profit:{symbol}"
        
        # Проверяем кэш
        cached_data = await self.redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            return {
                'order_id': data['order_id'],
                'price': Decimal(str(data['price'])),
                'quantity': Decimal(str(data['quantity'])),
                'status': data['status']
            }
        
        # Запрос к БД
        query = """
            SELECT order_id, price, quantity, status
            FROM take_profit_orders 
            WHERE symbol = ? AND status IN ('pending', 'partial_filled')
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        row = await db.execute_single(query, (symbol,))
        if not row:
            return None
        
        result = {
            'order_id': row['order_id'],
            'price': Decimal(str(row['price'])),
            'quantity': Decimal(str(row['quantity'])),
            'status': row['status']
        }
        
        # Кэшируем
        cache_data = {
            'order_id': result['order_id'],
            'price': str(result['price']),
            'quantity': str(result['quantity']),
            'status': result['status']
        }
        
        await self.redis_client.setex(
            cache_key, 
            self.cache_ttl, 
            json.dumps(cache_data)
        )
        
        return result
    
    async def update_take_profit(self, symbol: str, order_id: str, price: Decimal, quantity: Decimal):
        """Обновление тейк-профит ордера"""
        # Сначала отменяем старый ордер
        await self._cancel_old_take_profit(symbol)
        
        # Создаем новый
        query = """
            INSERT INTO take_profit_orders (symbol, order_id, price, quantity, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """
        
        params = (symbol, order_id, float(price), float(quantity), datetime.utcnow().isoformat())
        await db.execute_write(query, params)
        
        # Инвалидируем кэш
        await self.redis_client.delete(f"take_profit:{symbol}")
        
        logger.info(f"✅ Обновлен тейк-профит {symbol}: {price} x {quantity}")
    
    async def mark_take_profit_filled(self, order_id: str):
        """Отметка тейк-профита как исполненного"""
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
    
    async def _cancel_old_take_profit(self, symbol: str):
        """Отмена старого тейк-профит ордера"""
        query = """
            UPDATE take_profit_orders 
            SET status = 'cancelled'
            WHERE symbol = ? AND status IN ('pending', 'partial_filled')
        """
        
        await db.execute_write(query, (symbol,))
