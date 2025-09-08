from typing import List
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import logging

from config.constants import (
    GRID_COVERAGE_PERCENT,
    GRID_LEVELS,
    MARTINGALE_MULTIPLIER,
    TAKE_PROFIT_PERCENT,
    LEVERAGE,
    MARKET_ENTRY
)
from trading.models import OrderModel, OrderSide, OrderType, OrderStatus, TradingConfig

logger = logging.getLogger(__name__)

def calculate_grid_prices(current_price: Decimal, config: TradingConfig) -> List[Decimal]:
    """
    Рассчитывает цены для размещения грид-ордеров
    
    Args:
        current_price: Текущая цена актива
        config: Конфигурация торговли
        
    Returns:
        List[Decimal]: Список цен для размещения ордеров
    """
    prices = []
    
    # Минимальная цена (на coverage_percent ниже текущей)
    min_price = current_price * (Decimal('1') - Decimal(str(config.coverage_percent)))
    
    # Шаг между уровнями
    price_range = current_price - min_price
    step = price_range / Decimal(str(config.grid_levels - 1))
    
    # Генерируем цены от текущей вниз
    for i in range(config.grid_levels):
        price = current_price - (step * Decimal(str(i)))
        prices.append(price.quantize(Decimal('0.00001'), rounding=ROUND_DOWN))
    
    return prices

def calculate_martingale_quantities(
    base_quantity: Decimal, 
    config: TradingConfig
) -> List[Decimal]:
    """
    Рассчитывает количества для ордеров с мартингейлом
    
    Args:
        base_quantity: Базовое количество для первого ордера
        config: Конфигурация торговли
        
    Returns:
        List[Decimal]: Список количеств для каждого ордера
    """
    quantities = []
    multiplier = Decimal(str(config.martingale_multiplier))
    
    for i in range(config.grid_levels):
        if i == 0:
            quantity = base_quantity
        else:
            quantity = base_quantity * (multiplier ** i)
        
        quantities.append(quantity.quantize(Decimal('0.00001'), rounding=ROUND_DOWN))
    
    return quantities

def calculate_optimal_base_quantity(
    deposit_amount: Decimal, 
    current_price: Decimal, 
    config: TradingConfig
) -> Decimal:
    """
    Рассчитывает оптимальное базовое количество с учетом всех уровней
    
    Args:
        deposit_amount: Размер депозита
        current_price: Текущая цена актива
        config: Конфигурация торговли
        
    Returns:
        Decimal: Оптимальное базовое количество
    """
    # Доступная сумма с плечом
    available_amount = deposit_amount * Decimal(str(config.leverage))
    
    # Рассчитываем общий множитель всех ордеров
    total_multiplier = Decimal('0')
    multiplier = Decimal(str(config.martingale_multiplier))
    
    for i in range(config.grid_levels):
        if i == 0:
            total_multiplier += Decimal('1')
        else:
            total_multiplier += multiplier ** i
    
    # Базовое количество = доступная_сумма / (общий_множитель * цена)
    base_quantity = available_amount / (total_multiplier * current_price)
    
    return base_quantity.quantize(Decimal('0.00001'), rounding=ROUND_DOWN)

def build_grid(
    user_id: int,
    position_id: int,
    symbol: str,
    current_price: Decimal,
    deposit_amount: Decimal,
    config: TradingConfig = None
) -> List[OrderModel]:
    """
    Строит оптимизированную сетку ордеров для грид-торговли
    
    Args:
        user_id: ID пользователя
        position_id: ID позиции
        symbol: Торговый символ
        current_price: Текущая цена актива
        deposit_amount: Размер депозита
        config: Конфигурация торговли (опционально)
        
    Returns:
        List[OrderModel]: Список ордеров для размещения
    """
    if config is None:
        config = TradingConfig(
            leverage=LEVERAGE,
            grid_levels=GRID_LEVELS,
            martingale_multiplier=MARTINGALE_MULTIPLIER,
            coverage_percent=GRID_COVERAGE_PERCENT,
            take_profit_percent=TAKE_PROFIT_PERCENT
        )
    
    orders = []
    
    # Рассчитываем базовое количество
    base_quantity = calculate_optimal_base_quantity(
        deposit_amount=deposit_amount,
        current_price=current_price,
        config=config
    )
    
    # Логируем общую информацию о грид-сетке
    logger.info(f"🏗️ Построение грид-сетки для {symbol}:")
    logger.info(f"   💰 Депозит: {deposit_amount} USDT")
    logger.info(f"   📊 Текущая цена: {current_price}")
    logger.info(f"   ⚖️ Плечо: {config.leverage}x")
    logger.info(f"   🔢 Уровней грида: {config.grid_levels}")
    logger.info(f"   📈 Покрытие: {config.coverage_percent * 100}%")
    logger.info(f"   🔄 Мартингейл: {config.martingale_multiplier}x")
    logger.info(f"   📦 Базовое количество: {base_quantity}")
    
    # Рассчитываем цены для грида
    grid_prices = calculate_grid_prices(current_price, config)
    
    # Рассчитываем количества с мартингейлом
    quantities = calculate_martingale_quantities(base_quantity, config)
    
    # Создаем ордера
    for i, (price, quantity) in enumerate(zip(grid_prices, quantities)):
        # Первый ордер - рыночный при включенном MARKET_ENTRY
        if i == 0 and MARKET_ENTRY:
            order = OrderModel(
                user_id=user_id,
                position_id=position_id,
                order_id=f"market_{symbol}_{user_id}_{position_id}_{i}",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                price=current_price,
                quantity=quantity,
                status=OrderStatus.PENDING,
                grid_level=i,
                created_at=datetime.utcnow()
            )
        else:
            # Лимитные ордера
            order = OrderModel(
                user_id=user_id,
                position_id=position_id,
                order_id=f"limit_{symbol}_{user_id}_{position_id}_{i}",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=price,
                quantity=quantity,
                status=OrderStatus.PENDING,
                grid_level=i,
                created_at=datetime.utcnow()
            )
        
        orders.append(order)
        
        # Логируем параметры каждого ордера
        order_value = order.price * order.quantity
        margin_required = order_value / Decimal(str(config.leverage))
        
        if order.order_type == OrderType.MARKET:
            logger.info(f"   🎯 Ордер #{i+1:2d} (MARKET): "
                       f"💵 {order.quantity:.5f} @ {order.price:.5f} = {order_value:.2f} USDT "
                       f"(маржа: {margin_required:.2f})")
        else:
            price_diff_percent = ((order.price - current_price) / current_price * 100)
            logger.info(f"   📌 Ордер #{i+1:2d} (LIMIT):  "
                       f"💵 {order.quantity:.5f} @ {order.price:.5f} = {order_value:.2f} USDT "
                       f"(маржа: {margin_required:.2f}, {price_diff_percent:+.2f}%)")
    
    # Итоговая статистика
    total_value = sum(order.price * order.quantity for order in orders)
    total_margin = total_value / Decimal(str(config.leverage))
    logger.info(f"✅ Грид-сетка построена: {len(orders)} ордеров на {total_value:.2f} USDT "
               f"(требуется маржи: {total_margin:.2f} USDT)")
    
    return orders

def calculate_take_profit_price(average_price: Decimal, config: TradingConfig) -> Decimal:
    """
    Рассчитывает цену тейк-профита
    
    Args:
        average_price: Средняя цена входа
        config: Конфигурация торговли
        
    Returns:
        Decimal: Цена для тейк-профита
    """
    tp_multiplier = Decimal('1') + Decimal(str(config.take_profit_percent))
    take_profit_price = average_price * tp_multiplier
    return take_profit_price.quantize(Decimal('0.00001'), rounding=ROUND_DOWN)

def create_take_profit_order(
    user_id: int,
    position_id: int,
    symbol: str,
    average_price: Decimal,
    total_quantity: Decimal,
    config: TradingConfig = None
) -> OrderModel:
    """
    Создает ордер тейк-профита
    
    Args:
        user_id: ID пользователя
        position_id: ID позиции
        symbol: Торговый символ
        average_price: Средняя цена входа
        total_quantity: Общее количество для продажи
        config: Конфигурация торговли
        
    Returns:
        OrderModel: Ордер тейк-профита
    """
    if config is None:
        config = TradingConfig(take_profit_percent=TAKE_PROFIT_PERCENT)
    
    take_profit_price = calculate_take_profit_price(average_price, config)
    
    return OrderModel(
        user_id=user_id,
        position_id=position_id,
        order_id=f"tp_{symbol}_{user_id}_{position_id}",
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.TAKE_PROFIT,
        price=take_profit_price,
        quantity=total_quantity,
        status=OrderStatus.PENDING,
        created_at=datetime.utcnow()
    )

def validate_grid_parameters(
    current_price: Decimal,
    deposit_amount: Decimal,
    config: TradingConfig
) -> bool:
    """
    Валидация параметров грида перед построением
    
    Args:
        current_price: Текущая цена
        deposit_amount: Размер депозита
        config: Конфигурация торговли
        
    Returns:
        bool: True если параметры валидны
    """
    try:
        # Проверяем минимальные значения
        if current_price <= 0:
            return False
        
        if deposit_amount <= 0:
            return False
        
        if config.grid_levels < 2:
            return False
        
        if config.coverage_percent <= 0 or config.coverage_percent >= 1:
            return False
        
        if config.leverage < 1:
            return False
        
        # Проверяем что базовое количество будет больше 0
        base_quantity = calculate_optimal_base_quantity(
            deposit_amount, current_price, config
        )
        
        if base_quantity <= 0:
            return False
        
        return True
        
    except Exception:
        return False

def get_grid_statistics(orders: List[OrderModel]) -> dict:
    """
    Получение статистики по созданной сетке
    
    Args:
        orders: Список ордеров в сетке
        
    Returns:
        dict: Статистика грида
    """
    if not orders:
        return {}
    
    total_quantity = sum(order.quantity for order in orders)
    total_value = sum(order.price * order.quantity for order in orders)
    
    prices = [order.price for order in orders]
    min_price = min(prices)
    max_price = max(prices)
    
    market_orders = [o for o in orders if o.order_type == OrderType.MARKET]
    limit_orders = [o for o in orders if o.order_type == OrderType.LIMIT]
    
    return {
        "symbol": orders[0].symbol,
        "total_orders": len(orders),
        "market_orders_count": len(market_orders),
        "limit_orders_count": len(limit_orders),
        "total_quantity": float(total_quantity),
        "total_value_usdt": float(total_value),
        "average_price": float(total_value / total_quantity) if total_quantity > 0 else 0,
        "price_range": {
            "min": float(min_price),
            "max": float(max_price),
            "spread_percent": float((max_price - min_price) / max_price * 100)
        },
        "grid_levels": len(set(o.grid_level for o in orders if o.grid_level is not None)),
        "created_at": orders[0].created_at.isoformat() if orders[0].created_at else None
    }