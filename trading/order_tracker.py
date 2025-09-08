import asyncio
import logging
from typing import List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime
import json
from aiokafka import AIOKafkaProducer

from api.bitget_api import BitgetAPI
from database.repositories.limit_order_repo import LimitOrderRepository
from database.repositories.take_profit_repo import TakeProfitRepository
from config.constants import LEVERAGE, MARGIN_MODE, CHECK_DELAY, TAKE_PROFIT_PERCENT
from config.settings import settings
from trading.grid_builder import build_grid
from trading.models import OrderModel, OrderStatusUpdate, OrderStatus, KafkaOrderMessage, OrderSide, OrderType

logger = logging.getLogger(__name__)

class OrderTracker: 
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        """
        Инициализация трекера
        
        Args:
            api_key: API ключ
            api_secret: API секрет  
            api_passphrase: API пароль
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        
        self.limit_repo = LimitOrderRepository()
        self.tp_repo = TakeProfitRepository()
        
        # Kafka producer для уведомлений
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        self._kafka_started: bool = False

    async def start_kafka_producer(self) -> bool:
        """
        Запуск Kafka producer
        
        Returns:
            bool: True если producer успешно запущен
        """
        try:    
            self.kafka_producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_SERVERS,
                value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8'),
                request_timeout_ms=30000,
                retry_backoff_ms=100,
                max_block_ms=5000
            )
            
            await self.kafka_producer.start()
            self._kafka_started = True
            
            logger.info("✅ Kafka producer запущен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Kafka producer: {e}")
            self.kafka_producer = None
            self._kafka_started = False
            return False

    async def stop_kafka_producer(self) -> None:
        """Остановка Kafka producer"""
        try:
            if self.kafka_producer and self._kafka_started:
                await self.kafka_producer.stop()
                logger.info("✅ Kafka producer остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки Kafka producer: {e}")
        finally:
            self.kafka_producer = None
            self._kafka_started = False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_kafka_producer()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_kafka_producer()

    async def start_trading_for_symbol(self, symbol: str, deposit_amount: Decimal = Decimal('100')) -> bool:
        """
        Запуск торговли для конкретного символа
        
        Args:
            symbol: Торговый символ
            deposit_amount: Размер депозита в USDT
            
        Returns:
            bool: True если успешно запущена торговля
        """
        try:
            logger.info(f"🚀 Запуск торговли для {symbol}")
            
            # 1. Инициализируем API и устанавливаем настройки
            api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
            
            # Устанавливаем плечо и режим маржи
            leverage_ok = await api.set_leverage(symbol, LEVERAGE)
            
            if not leverage_ok:
                logger.error(f"❌ Не удалось установить настройки для {symbol}")
                return False
            
            # 2. Получаем текущую цену
            current_price = await api.get_ticker_price(symbol)
            if not current_price:
                logger.error(f"❌ Не удалось получить цену {symbol}")
                return False
            
            # 3. Строим сетку ордеров
            orders = build_grid(
                user_id=1,  # Пока хардкод, потом можно параметризовать
                position_id=1,
                symbol=symbol,
                current_price=current_price,
                deposit_amount=deposit_amount
            )
            
            # 4. Размещаем ордера на бирже
            placed_orders = []
            for order in orders:
                if order.order_type == OrderType.MARKET:
                    # Рыночный ордер - используем номинал в USDT
                    notional_usdt = float(order.quantity * order.price)
                    result = await api.create_market_order(symbol, order.side, notional_usdt)
                else:
                    # Лимитный ордер
                    result = await api.create_limit_order(symbol, order.side, order.quantity, order.price)
                
                if result:
                    # Обновляем ID ордера с биржи
                    order.order_id = result.order_id
                    order.user_id = result.user_id
                    order.position_id = result.position_id
                    
                    # Сохраняем в БД
                    await self.limit_repo.save_order(order)
                    placed_orders.append(order)
                    
                    # Отправляем уведомление в Kafka
                    await self._send_order_notification(order)
                    
                    logger.info(f"✅ Размещен ордер {order.order_id} {order.side} {symbol}")
                
                # Небольшая задержка между ордерами
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ Сетка открыта для {symbol}: {len(placed_orders)}/{len(orders)} ордеров")
            return len(placed_orders) > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли {symbol}: {e}")
            return False

    async def track_symbol_orders(self, symbol: str) -> Optional[str]:
        """
        Отслеживание ордеров для символа
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Optional[str]: 'restart' если нужен перезапуск, None если продолжаем
        """
        try:
            # 1. Проверяем тейк-профит
            tp_result = await self._check_take_profit(symbol)
            if tp_result == 'filled':
                logger.info(f"🎯 Тейк-профит исполнен для {symbol} - требуется перезапуск")
                return 'restart'
            
            # 2. Получаем активные лимитные ордера  
            active_order_ids = await self.limit_repo.get_active_orders_ids(symbol)
            
            if not active_order_ids:
                logger.debug(f"Нет активных ордеров для {symbol}")
                return None
            
            # 3. Проверяем ордера последовательно (оптимизация)
            updates, should_update_tp = await self._check_limit_orders_optimized(symbol, active_order_ids)
            
            # 4. Применяем обновления батчом
            if updates:
                await self.limit_repo.batch_update_order_statuses(updates)
            
            # 5. Обновляем тейк-профит если нужно
            if should_update_tp:
                await self._update_take_profit(symbol)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка отслеживания {symbol}: {e}")
            return None

    async def _check_take_profit(self, symbol: str) -> Optional[str]:
        """
        Проверка статуса тейк-профита
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Optional[str]: Статус тейк-профита
        """
        try:
            tp_order = await self.tp_repo.get_active_take_profit(symbol)
            if not tp_order:
                return None
            
            # Создаем API соединение для проверки
            api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
            order_info = await api.fetch_order(tp_order.order_id, symbol)
            
            if order_info:
                status = order_info.get('status', 'unknown')
                
                if status in ['closed', 'filled']:
                    # Тейк-профит исполнен
                    await self.tp_repo.mark_filled(tp_order.order_id)
                    
                    # Отменяем все оставшиеся ордера
                    await self._cancel_remaining_orders(symbol)
                    
                    return 'filled'
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки тейк-профита {symbol}: {e}")
            return None

    async def _check_limit_orders_optimized(self, symbol: str, order_ids: List[str]) -> Tuple[List[OrderStatusUpdate], bool]:
        """
        Оптимизированная проверка лимитных ордеров
        
        Args:
            symbol: Торговый символ
            order_ids: Список ID ордеров
            
        Returns:
            Tuple[List[OrderStatusUpdate], bool]: Список обновлений и флаг обновления ТП
        """
        updates = []
        should_update_tp = False
        
        api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
        
        try:
            for order_id in order_ids:
                # Проверяем кэш статуса
                cached_status = await self.limit_repo.get_order_status_cached(order_id)
                if cached_status == 'filled':
                    continue  # Пропускаем уже исполненные
                
                # Проверяем на бирже
                order_info = await api.fetch_order(order_id, symbol)
                if not order_info:
                    continue
                
                status = order_info.get('status', 'unknown')
                filled_qty = order_info.get('filled', 0)
                
                if status == 'open':
                    # Ордер не исполнен - останавливаем проверку (оптимизация)
                    break
                    
                elif status in ['closed', 'filled', 'partial-filled']:
                    # Ордер исполнен
                    update = OrderStatusUpdate(
                        order_id=order_id,
                        status=OrderStatus.FILLED if status in ['closed', 'filled'] else OrderStatus.PARTIAL_FILLED,
                        filled_quantity=Decimal(str(filled_qty)) if filled_qty else None,
                        filled_at=datetime.utcnow()
                    )
                    
                    updates.append(update)
                    should_update_tp = True
                    
                    # Если частично исполнен - тоже останавливаем проверку
                    if status == 'partial-filled':
                        break
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.05)
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ордеров {symbol}: {e}")
        
        return updates, should_update_tp

    async def _update_take_profit(self, symbol: str):
        """
        Обновление тейк-профита на основе исполненных ордеров
        
        Args:
            symbol: Торговый символ
        """
        try:
            # Получаем сводку по исполненным ордерам
            summary = await self.limit_repo.get_filled_orders_summary(symbol)
            
            if summary['total_quantity'] == 0:
                return
            
            # Рассчитываем цену тейк-профита
            avg_price = summary['weighted_price']
            tp_price = avg_price * Decimal(str(1 + TAKE_PROFIT_PERCENT))
            total_quantity = summary['total_quantity']
            
            # Отменяем старый тейк-профит
            current_tp = await self.tp_repo.get_active_take_profit(symbol)
            if current_tp:
                api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
                await api.cancel_order(current_tp.order_id, symbol)
            
            # Создаем новый тейк-профит на бирже
            api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
            tp_order = await api.create_limit_order(
                symbol=symbol,
                side=OrderSide.SELL,
                amount=total_quantity,
                price=tp_price
            )
            
            if tp_order:
                # Сохраняем в БД
                await self.tp_repo.create_take_profit(
                    symbol=symbol,
                    order_id=tp_order.order_id,
                    price=tp_price,
                    quantity=total_quantity
                )
                
                logger.info(f"🎯 Обновлен тейк-профит {symbol}: {tp_price} x {total_quantity}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления тейк-профита {symbol}: {e}")

    async def _cancel_remaining_orders(self, symbol: str):
        """
        Отмена всех оставшихся ордеров после исполнения тейк-профита
        
        Args:
            symbol: Торговый символ
        """
        try:
            active_orders = await self.limit_repo.get_active_orders_ids(symbol)
            
            if not active_orders:
                return
            
            api = BitgetAPI(self.api_key, self.api_secret, self.api_passphrase)
            updates = []
            
            for order_id in active_orders:
                success = await api.cancel_order(order_id, symbol)
                if success:
                    updates.append(OrderStatusUpdate(
                        order_id=order_id,
                        status=OrderStatus.CANCELLED
                    ))
                
                await asyncio.sleep(0.05)
            
            # Батчевое обновление статусов
            if updates:
                await self.limit_repo.batch_update_order_statuses(updates)
            
            logger.info(f"✅ Отменено {len(updates)} ордеров для {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордеров {symbol}: {e}")

    async def _send_order_notification(self, order: OrderModel) -> bool:
        """
        Отправка уведомления в Kafka о создании ордера
        
        Args:
            order: Модель ордера
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        try:
            message = KafkaOrderMessage(
                symbol=order.symbol,
                order_id=order.order_id,
                side=order.side,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                user_id=order.user_id
            )
            
            # Используем model_dump() вместо устаревшего dict()
            await self.kafka_producer.send(
                settings.KAFKA_TOPIC_NOTIFICATIONS,
                value=message.model_dump()
            )
            
            logger.debug(f"✅ Уведомление отправлено для ордера {order.order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления для {order.order_id}: {e}")
            return False