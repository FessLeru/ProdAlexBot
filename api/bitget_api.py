import ccxt.async_support as ccxt
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

from utils.rate_limiter import RateLimiter
from trading.models import OrderSide, OrderType
from config.settings import settings

logger = logging.getLogger(__name__)

class BitgetAPI:    
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        self.exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_passphrase,
            'sandbox': False,
            'enableRateLimit': True,
            'rateLimit': 100,  # мс между запросами
            'options': {
                'defaultType': 'swap',  # для фьючерсов
            }
        })
        
        self.rate_limiter = RateLimiter(
            max_requests=settings.MAX_REQUESTS_PER_MINUTE,
            window=settings.RATE_LIMIT_WINDOW
        )
        
        self._session_active = False

    async def __aenter__(self):
        """Асинхронный контекст-менеджер"""
        self._session_active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        await self.close()

    async def close(self):
        """Закрытие соединения"""
        if self._session_active:
            await self.exchange.close()
            self._session_active = False

    async def test_connection(self) -> bool:
        """Тестирование подключения и API ключей"""
        try:
            await self.rate_limiter.acquire("test_connection")
            balance = await self.exchange.fetch_balance()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования подключения: {e}")
            return False

    async def get_account_balance(self) -> Optional[Dict]:
        """Получение баланса аккаунта"""
        try:
            await self.rate_limiter.acquire("balance")
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return None

    async def get_ticker_price(self, symbol: str) -> Optional[Decimal]:
        """Получение текущей цены тикера"""
        try:
            await self.rate_limiter.acquire(f"ticker_{symbol}")
            ticker = await self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker['last']))
        except Exception as e:
            logger.error(f"❌ Ошибка получения цены {symbol}: {e}")
            return None

    async def create_market_order(self, symbol: str, side: OrderSide, amount: Decimal, margin_coin: str = "USDT") -> Optional[Dict]:
        """Создание маркет-ордера для фьючерсов"""
        try:
            await self.rate_limiter.acquire(f"create_order_{symbol}")
            
            params = {
                'marginCoin': margin_coin,
                'marginMode': 'cross',
                'productType': 'USDT-FUTURES'  # Явно указываем тип продукта
            }
            
            order = await self.exchange.create_market_order(
                symbol=symbol,
                side=side.value,
                amount=float(amount),
                params=params
            )
            
            logger.info(f"✅ Создан маркет-ордер {order['id']} {side.value} {amount} {symbol}")
            return order
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания маркет-ордера {symbol}: {e}")
            return None

    async def create_limit_order(self, symbol: str, side: OrderSide, amount: Decimal, price: Decimal) -> Optional[Dict]:
        """Создание лимит-ордера"""
        try:
            await self.rate_limiter.acquire(f"create_order_{symbol}")
            order = await self.exchange.create_limit_order(
                symbol=symbol,
                side=side.value,
                amount=float(amount),
                price=float(price),
                params={
                    'marginCoin': 'USDT',
                    'marginMode': 'cross'
                }
            )
            
            logger.info(f"✅ Создан лимит-ордер {order['id']} {side.value} {amount} {symbol} @ {price}")
            return order
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания лимит-ордера {symbol}: {e}")
            return None

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Отмена ордера"""
        try:
            await self.rate_limiter.acquire(f"cancel_order_{symbol}")
            
            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Отменен ордер {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордера {order_id}: {e}")
            return False

    async def fetch_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        """Получение информации об ордере"""
        try:
            await self.rate_limiter.acquire(f"fetch_order_{symbol}")
            
            order = await self.exchange.fetch_order(order_id, symbol)
            return order
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения ордера {order_id}: {e}")
            return None

    async def fetch_orders_batch(self, symbol: str, order_ids: List[str]) -> Dict[str, Dict]:
        """Батчевое получение ордеров (если поддерживается API)"""
        results = {}
        
        # Bitget может не поддерживать batch запросы, делаем последовательно
        for order_id in order_ids:
            order_info = await self.fetch_order(order_id, symbol)
            if order_info:
                results[order_id] = order_info
            
            # Небольшая задержка между запросами
            await asyncio.sleep(0.05)
        
        return results

    async def get_open_positions(self) -> List[Dict]:
        """Получение открытых позиций"""
        try:
            await self.rate_limiter.acquire("positions")
            
            positions = await self.exchange.fetch_positions()
            # Фильтруем только открытые позиции
            open_positions = [pos for pos in positions if pos['size'] != 0]
            
            return open_positions
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения позиций: {e}")
            return []

    async def set_leverage(self, symbol: str, leverage: int, margin_coin: str = "USDT") -> bool:
        """Установка плеча"""
        try:
            await self.rate_limiter.acquire(f"leverage_{symbol}")
            
            params = {
                'marginCoin': margin_coin
            }
            
            await self.exchange.set_leverage(leverage, symbol, params=params)
            logger.info(f"✅ Установлено плечо {leverage}x для {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки плеча для {symbol}: {e}")
            return False

    async def set_margin_mode(self, symbol: str, margin_mode: str = "cross", margin_coin: str = "USDT") -> bool:
        """Установка режима маржи"""
        try:
            await self.rate_limiter.acquire(f"margin_mode_{symbol}")
            
            # Специфичный для Bitget запрос с marginCoin
            params = {
                'symbol': symbol,
                'marginMode': margin_mode,
                'marginCoin': margin_coin
            }
            
            await self.exchange.set_margin_mode(margin_mode, symbol, params=params)
            logger.info(f"✅ Установлен режим маржи {margin_mode} для {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки режима маржи для {symbol}: {e}")
            return False

    async def get_order_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Получение истории ордеров"""
        try:
            await self.rate_limiter.acquire(f"history_{symbol}")
            
            orders = await self.exchange.fetch_orders(symbol, limit=limit)
            return orders
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории ордеров {symbol}: {e}")
            return []

    def get_api_stats(self) -> Dict:
        """Получение статистики использования API"""
        return self.rate_limiter.get_stats()
