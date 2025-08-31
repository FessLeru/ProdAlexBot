import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from fake_useragent import UserAgent

from api.bitget_api import BitgetAPI
from database.repositories.limit_order_repo import LimitOrderRepository
from database.repositories.take_profit_repo import TakeProfitRepository
from config.constants import COINS, CHECK_DELAY

logger = logging.getLogger(__name__)

class OrderTracker:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        # Инициализируем API с fake user agent
        ua = UserAgent()
        self.api = BitgetAPI(api_key, api_secret, api_passphrase)
        self.api.exchange.headers['User-Agent'] = ua.random
        
        self.limit_repo = LimitOrderRepository()
        self.tp_repo = TakeProfitRepository()
    
    async def track_symbol(self, symbol: str):
        """Основная функция отслеживания символа"""
        logger.info(f"🎯 Начинаем отслеживание {symbol}")
        
        while True:
            try:
                # 1. Проверяем тейк-профит
                tp_order = await self.tp_repo.get_take_profit(symbol)
                
                if tp_order:
                    tp_status = await self._check_take_profit_status(symbol, tp_order['order_id'])
                    
                    if tp_status == 'filled':
                        logger.info(f"✅ Тейк-профит исполнен для {symbol}, ожидание 60 сек")
                        await self.tp_repo.mark_take_profit_filled(tp_order['order_id'])
                        #TODO: close the grid
                        await asyncio.sleep(60)  # Ожидание для новых участников
                        continue
                
                # 2. Получаем лимитные ордера
                limit_order_ids = await self.limit_repo.get_orders_ids(symbol)
                
                if not limit_order_ids:
                    logger.debug(f"Нет активных ордеров для {symbol}")
                    await asyncio.sleep(CHECK_DELAY)
                    continue
                
                # 3. Проверяем ордера последовательно
                filled_orders, should_recalculate = await self._check_limit_orders(symbol, limit_order_ids)
                
                # 4. Пересчитываем тейк-профит если нужно
                if should_recalculate and filled_orders:
                    await self._recalculate_take_profit(symbol, filled_orders)
                
                await asyncio.sleep(CHECK_DELAY)
                
            except Exception as e:
                logger.error(f"❌ Ошибка отслеживания {symbol}: {e}")
                await asyncio.sleep(CHECK_DELAY * 2)  # Увеличенная пауза при ошибке
    
    async def _check_take_profit_status(self, symbol: str, tp_order_id: str) -> str:
        """Проверка статуса тейк-профита"""
        try:
            order_info = await self.api.fetch_order(tp_order_id, symbol)
            if order_info:
                return order_info.get('status', 'unknown')
            return 'unknown'
        except Exception as e:
            logger.error(f"❌ Ошибка проверки тейк-профита {tp_order_id}: {e}")
            return 'unknown'
    
    async def _check_limit_orders(self, symbol: str, order_ids: List[str]) -> Tuple[List[Dict], bool]:
        """Проверка лимитных ордеров"""
        filled_orders = []
        should_recalculate = False
        batch_updates = []
        
        for order_id in order_ids:
            # Пропускаем уже исполненные ордера из кэша
            cached_status = await self.limit_repo.get_order_status(order_id)
            if cached_status == 'filled':
                continue
            
            # Проверяем статус на бирже
            try:
                order_info = await self.api.fetch_order(order_id, symbol)
                if not order_info:
                    continue
                
                status = order_info.get('status', 'unknown')
                filled_qty = Decimal(str(order_info.get('filled', 0)))
                
                if status == 'open':
                    # Ордер не исполнен - прекращаем проверку
                    break
                    
                elif status in ['partial-filled', 'filled']:
                    # Ордер исполнен частично или полностью
                    filled_orders.append({
                        'order_id': order_id,
                        'price': Decimal(str(order_info.get('price', 0))),
                        'filled_quantity': filled_qty,
                        'status': 'filled' if status == 'filled' else 'partial_filled'
                    })
                    
                    # Подготавливаем для batch update
                    batch_updates.append((
                        'filled' if status == 'filled' else 'partial_filled',
                        float(filled_qty),
                        datetime.utcnow().isoformat(),
                        order_id
                    ))
                    
                    should_recalculate = True
                    
                    # Если частично исполнен - тоже прекращаем проверку
                    if status == 'partial-filled':
                        break
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка проверки ордера {order_id}: {e}")
                break
        
        # Батчевое обновление БД
        if batch_updates:
            await self.limit_repo.batch_update_filled_orders(batch_updates)
        
        return filled_orders, should_recalculate
    
    async def _recalculate_take_profit(self, symbol: str, new_filled_orders: List[Dict]):
        """Пересчет и обновление тейк-профита"""
        try:
            # Получаем все исполненные ордера
            all_filled = await self.limit_repo.get_filled_orders_for_symbol(symbol)
            
            if not all_filled:
                return
            
            # Рассчитываем среднюю цену и общий объем
            total_quantity = Decimal('0')
            weighted_sum = Decimal('0')
            
            for order in all_filled:
                quantity = order['quantity']
                price = order['price']
                total_quantity += quantity
                weighted_sum += price * quantity
            
            if total_quantity == 0:
                return
            
            avg_price = weighted_sum / total_quantity
            tp_price = avg_price * Decimal('1.02')  # +2%
            
            # Отменяем старый тейк-профит на бирже
            current_tp = await self.tp_repo.get_take_profit(symbol)
            if current_tp:
                await self.api.cancel_order(current_tp['order_id'], symbol)
            
            # Создаем новый тейк-профит
            tp_order = await self.api.create_limit_order(
                symbol=symbol,
                side='sell',  # Закрываем лонг позицию
                amount=total_quantity,
                price=tp_price
            )
            
            if tp_order:
                await self.tp_repo.update_take_profit(
                    symbol=symbol,
                    order_id=tp_order['id'],
                    price=tp_price,
                    quantity=total_quantity
                )
                
                logger.info(f"🎯 Обновлен тейк-профит {symbol}: {tp_price} x {total_quantity}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка пересчета тейк-профита {symbol}: {e}")