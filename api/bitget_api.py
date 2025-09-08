import ccxt.async_support as ccxt
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging
from fake_useragent import UserAgent

from utils.rate_limiter import RateLimiter
from trading.models import OrderSide, OrderType, OrderModel, OrderStatus
from config.settings import settings

logger = logging.getLogger(__name__)

class BitgetAPI:
    """
    Оптимизированный API клиент для Bitget с поддержкой ccxt 4.5.3
    """
    
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        """
        Инициализация API клиента
        
        Args:
            api_key: API ключ
            api_secret: API секрет  
            api_passphrase: API пароль
        """
        ua = UserAgent()
        
        self.exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_passphrase,
            'sandbox': False,
            'enableRateLimit': True,
            'rateLimit': 300,
            'timeout': 30000,
            'options': {
                'defaultType': 'swap',
                'fetchCurrencies': False,
            },
            'headers': {
                'User-Agent': ua.random
            }
        })
        
        # Уменьшенный rate limit из-за fake user agent
        self.rate_limiter = RateLimiter(
            max_requests=100,
            window=60,
            max_concurrent=5
        )

    async def close(self):
        """Явное закрытие соединения"""
        try:
            await self.exchange.close()
        except Exception as e:
            logger.error(f"Ошибка закрытия соединения: {e}")

    async def test_connection(self) -> bool:
        """
        Тестирование подключения и API ключей
        
        Returns:
            bool: True если подключение успешно
        """
        try:
            await self.rate_limiter.acquire("test_connection")
            await self.exchange.load_markets(reload=True, params={"type": "swap"})
            balance = await self.exchange.fetch_balance()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования подключения: {e}")
            return False
        finally:
            await self.close()

    async def get_account_balance(self) -> Optional[Dict]:
        """
        Получение баланса аккаунта
        
        Returns:
            Optional[Dict]: Баланс или None при ошибке
        """
        try:
            await self.rate_limiter.acquire("balance")
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return None
        finally:
            await self.close()

    async def get_ticker_price(self, symbol: str) -> Optional[Decimal]:
        """
        Получение текущей цены тикера
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Optional[Decimal]: Цена или None при ошибке
        """
        try:
            await self.rate_limiter.acquire(f"ticker_{symbol}")
            ticker = await self.exchange.fetch_ticker(symbol)
            price = ticker.get('last') or ticker.get('close')
            if price:
                return Decimal(str(price))
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения цены {symbol}: {e}")
            return None
        finally:
            await self.close()

    async def get_size_from_notional(self, symbol: str, notional_usdt: float) -> Optional[float]:
        """
        Расчет размера позиции из номинала в USDT
        
        Args:
            symbol: Торговый символ
            notional_usdt: Номинал в USDT
            
        Returns:
            Optional[float]: Размер позиции или None при ошибке
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            last = ticker.get("last") or ticker.get("close")
            if not last:
                return None

            market = self.exchange.market(symbol)
            contract_size = market.get("contractSize", 1)

            raw_size = Decimal(str(notional_usdt)) / (Decimal(str(last)) * Decimal(str(contract_size)))
            raw_size = raw_size.quantize(Decimal("1.00000000"))
            return float(self.exchange.amount_to_precision(symbol, float(raw_size)))
        except Exception as e:
            logger.error(f"❌ Ошибка расчета размера для {symbol}: {e}")
            return None

    async def create_market_order(self, symbol: str, side: OrderSide, notional_usdt: float) -> Optional[OrderModel]:
        """
        Создание маркет-ордера по номиналу в USDT
        
        Args:
            symbol: Торговый символ
            side: Сторона ордера
            notional_usdt: Номинал в USDT
            
        Returns:
            Optional[OrderModel]: Модель ордера или None при ошибке
        """
        try:
            await self.rate_limiter.acquire(f"create_market_{symbol}")
            
            # Загружаем рынки если нужно
            if not self.exchange.markets:
                await self.exchange.load_markets(reload=True, params={"type": "swap"})
            
            # Рассчитываем размер
            size = await self.get_size_from_notional(symbol, notional_usdt)
            if not size:
                return None
            
            params = {
                'marginMode': 'cross',
                'marginCoin': 'USDT',
                'timeInForceValue': 'normal',
            }
            
            order = await self.exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=size,
                params=params
            )
            
            # Получаем текущую цену для модели
            current_price = await self.get_ticker_price(symbol)
            
            order_model = OrderModel(
                user_id=0,  # Будет заполнено в вызывающем коде
                position_id=0,  # Будет заполнено в вызывающем коде
                order_id=order['id'],
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                price=current_price or Decimal('0'),
                quantity=Decimal(str(size)),
                status=OrderStatus.PENDING
            )
            
            logger.info(f"✅ Создан маркет-ордер {order['id']} {side} {size} {symbol}")
            return order_model
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания маркет-ордера {symbol}: {e}")
            return None
        finally:
            await self.close()

    async def create_limit_order(self, symbol: str, side: OrderSide, amount: Decimal, price: Decimal) -> Optional[OrderModel]:
        """
        Создание лимит-ордера
        
        Args:
            symbol: Торговый символ
            side: Сторона ордера
            amount: Количество
            price: Цена
            
        Returns:
            Optional[OrderModel]: Модель ордера или None при ошибке
        """
        try:
            await self.rate_limiter.acquire(f"create_limit_{symbol}")
            
            params = {
                'marginMode': 'cross',
                'marginCoin': 'USDT',
                'timeInForceValue': 'normal',
            }
            
            order = await self.exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=float(amount),
                price=float(price),
                params=params
            )
            
            order_model = OrderModel(
                user_id=0,  # Будет заполнено в вызывающем коде
                position_id=0,  # Будет заполнено в вызывающем коде
                order_id=order['id'],
                symbol=symbol,
                side=side,
                order_type=OrderType.LIMIT,
                price=price,
                quantity=amount,
                status=OrderStatus.PENDING
            )
            
            logger.info(f"✅ Создан лимит-ордер {order['id']} {side} {amount} {symbol} @ {price}")
            return order_model
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания лимит-ордера {symbol}: {e}")
            return None
        finally:
            await self.close()

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Отмена ордера
        
        Args:
            order_id: ID ордера
            symbol: Торговый символ
            
        Returns:
            bool: True если успешно отменен
        """
        try:
            await self.rate_limiter.acquire(f"cancel_{symbol}")
            await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Отменен ордер {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отмены ордера {order_id}: {e}")
            return False
        finally:
            await self.close()

    async def fetch_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        """
        Получение информации об ордере
        
        Args:
            order_id: ID ордера
            symbol: Торговый символ
            
        Returns:
            Optional[Dict]: Информация об ордере или None при ошибке
        """
        try:
            await self.rate_limiter.acquire(f"fetch_{symbol}")
            order = await self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"❌ Ошибка получения ордера {order_id}: {e}")
            return None
        finally:
            await self.close()

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Установка плеча
        
        Args:
            symbol: Торговый символ
            leverage: Размер плеча
            
        Returns:
            bool: True если успешно установлено
        """
        try:
            await self.rate_limiter.acquire(f"leverage_{symbol}")
            params = {'marginCoin': 'USDT'}
            await self.exchange.set_leverage(leverage, symbol, params=params)
            logger.info(f"✅ Установлено плечо {leverage}x для {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки плеча для {symbol}: {e}")
            return False
        finally:
            await self.close()

    async def set_margin_mode(self, symbol: str, margin_mode: str = "cross") -> bool:
        """
        Установка режима маржи
        
        Args:
            symbol: Торговый символ
            margin_mode: Режим маржи
            
        Returns:
            bool: True если успешно установлен
        """
        try:
            await self.rate_limiter.acquire(f"margin_{symbol}")
            params = {
                'symbol': symbol,
                'marginMode': margin_mode,
                'marginCoin': 'USDT'
            }
            await self.exchange.set_margin_mode(margin_mode, symbol, params=params)
            logger.info(f"✅ Установлен режим маржи {margin_mode} для {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка установки режима маржи для {symbol}: {e}")
            return False
        finally:
            await self.close()

    def get_api_stats(self) -> Dict:
        """
        Получение статистики использования API
        
        Returns:
            Dict: Статистика rate limiter
        """
        return self.rate_limiter.get_stats()