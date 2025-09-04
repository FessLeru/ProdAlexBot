from typing import List, Tuple, Dict
from decimal import Decimal, ROUND_DOWN
from datetime import datetime

from config.constants import (
    GRID_COVERAGE_PERCENT,
    GRID_LEVELS,
    MARTINGALE_MULTIPLIER,
    TAKE_PROFIT_PERCENT,
    LEVERAGE,
    MARGIN_MODE,
    MARKET_ENTRY
)
from trading.models import OrderModel, OrderSide, OrderType, OrderStatus


def calculate_grid_prices(current_price: Decimal, grid_levels: int, coverage_percent: float) -> List[Decimal]:
    """
    Рассчитывает цены для размещения грид-ордеров.
    
    Args:
        current_price (Decimal): Текущая цена актива.
        grid_levels (int): Количество уровней в сетке.
        coverage_percent (float): Процент покрытия вниз от текущей цены.
        
    Returns:
        List[Decimal]: Список цен для размещения ордеров (от текущей цены вниз).
    """
    prices: List[Decimal] = []
    
    # Рассчитываем минимальную цену (на 40% ниже текущей)
    min_price: Decimal = current_price * Decimal(1 - coverage_percent)
    
    # Рассчитываем шаг между уровнями
    price_range: Decimal = current_price - min_price
    step: Decimal = price_range / Decimal(grid_levels - 1)
    
    # Генерируем цены от текущей цены вниз
    for i in range(grid_levels):
        price: Decimal = current_price - (step * Decimal(i))
        prices.append(price.quantize(Decimal('0.00001'), rounding=ROUND_DOWN))
    
    return prices


def calculate_martingale_quantities(
    base_quantity: Decimal, 
    grid_levels: int, 
    martingale_multiplier: float
) -> List[Decimal]:
    """
    Рассчитывает количества для ордеров с учётом мартингейла.
    
    Args:
        base_quantity (Decimal): Базовое количество для первого ордера.
        grid_levels (int): Количество уровней в сетке.
        martingale_multiplier (float): Множитель мартингейла.
        
    Returns:
        List[Decimal]: Список количеств для каждого ордера.
    """
    quantities: List[Decimal] = []
    
    for i in range(grid_levels):
        # Первый ордер - базовое количество, остальные увеличиваются
        if i == 0:
            quantity = base_quantity
        else:
            quantity = base_quantity * (Decimal(str(martingale_multiplier)) ** i)
        
        quantities.append(quantity.quantize(Decimal('0.00001'), rounding=ROUND_DOWN))
    
    return quantities


def calculate_base_quantity(
    deposit_amount: Decimal, 
    current_price: Decimal, 
    leverage: int,
    grid_levels: int,
    martingale_multiplier: float
) -> Decimal:
    """
    Рассчитывает базовое количество для первого ордера с учётом всех уровней.
    
    Args:
        deposit_amount (Decimal): Размер депозита.
        current_price (Decimal): Текущая цена актива.
        leverage (int): Плечо.
        grid_levels (int): Количество уровней в сетке.
        martingale_multiplier (float): Множитель мартингейла.
        
    Returns:
        Decimal: Базовое количество для первого ордера.
    """
    # Доступная сумма с учётом плеча
    available_amount: Decimal = deposit_amount * Decimal(leverage)
    
    # Рассчитываем общий множитель для всех ордеров
    total_multiplier: Decimal = Decimal('0')
    for i in range(grid_levels):
        if i == 0:
            total_multiplier += Decimal('1')
        else:
            total_multiplier += Decimal(str(martingale_multiplier)) ** i
    
    # Базовое количество = доступная_сумма / (общий_множитель * цена)
    base_quantity: Decimal = available_amount / (total_multiplier * current_price)
    
    return base_quantity.quantize(Decimal('0.00001'), rounding=ROUND_DOWN)


def build_grid(
    user_id: int,
    position_id: int,
    symbol: str,
    current_price: Decimal,
    deposit_amount: Decimal
) -> List[OrderModel]:
    """
    Строит сетку ордеров для грид-торговли.
    
    Args:
        user_id (int): ID пользователя.
        position_id (int): ID позиции.
        symbol (str): Торговый символ.
        current_price (Decimal): Текущая цена актива.
        deposit_amount (Decimal): Размер депозита пользователя.
        
    Returns:
        List[OrderModel]: Список ордеров для размещения.
    """
    orders: List[OrderModel] = []
    
    # Рассчитываем базовое количество
    base_quantity: Decimal = calculate_base_quantity(
        deposit_amount=deposit_amount,
        current_price=current_price,
        leverage=LEVERAGE,
        grid_levels=GRID_LEVELS,
        martingale_multiplier=MARTINGALE_MULTIPLIER
    )
    
    # Рассчитываем цены для размещения ордеров
    grid_prices: List[Decimal] = calculate_grid_prices(
        current_price=current_price,
        grid_levels=GRID_LEVELS,
        coverage_percent=GRID_COVERAGE_PERCENT
    )
    
    # Рассчитываем количества с учётом мартингейла
    quantities: List[Decimal] = calculate_martingale_quantities(
        base_quantity=base_quantity,
        grid_levels=GRID_LEVELS,
        martingale_multiplier=MARTINGALE_MULTIPLIER
    )
    
    # Создаём ордера
    for i, (price, quantity) in enumerate(zip(grid_prices, quantities)):
        # Первый ордер - рыночный (покупаем сразу по маркету)
        if i == 0 and MARKET_ENTRY:
            order = OrderModel(
                user_id=user_id,
                position_id=position_id,
                order_id=f"market_{symbol}_{user_id}_{position_id}",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                price=current_price,  # Для рыночного ордера цена = текущая цена
                quantity=quantity,
                status=OrderStatus.PENDING,
                grid_level=i,
                created_at=datetime.now()
            )
        else:
            # Остальные ордера - лимитные
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
                created_at=datetime.now()
            )
        
        orders.append(order)
    
    return orders


def calculate_take_profit_price(average_price: Decimal, take_profit_percent: float) -> Decimal:
    """
    Рассчитывает цену тейк-профита.
    
    Args:
        average_price (Decimal): Средняя цена входа.
        take_profit_percent (float): Процент тейк-профита.
        
    Returns:
        Decimal: Цена для тейк-профита.
    """
    take_profit_price: Decimal = average_price * Decimal(1 + take_profit_percent)
    return take_profit_price.quantize(Decimal('0.00001'), rounding=ROUND_DOWN)


def create_take_profit_order(
    user_id: int,
    position_id: int,
    symbol: str,
    average_price: Decimal,
    total_quantity: Decimal
) -> OrderModel:
    """
    Создаёт ордер тейк-профита.
    
    Args:
        user_id (int): ID пользователя.
        position_id (int): ID позиции.
        symbol (str): Торговый символ.
        average_price (Decimal): Средняя цена входа.
        total_quantity (Decimal): Общее количество для продажи.
        
    Returns:
        OrderModel: Ордер тейк-профита.
    """
    take_profit_price: Decimal = calculate_take_profit_price(
        average_price=average_price,
        take_profit_percent=TAKE_PROFIT_PERCENT
    )
    
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
        created_at=datetime.now()
    )


def get_grid_summary(orders: List[OrderModel]) -> Dict[str, any]:
    """
    Возвращает сводку по созданной сетке ордеров.
    
    Args:
        orders (List[OrderModel]): Список ордеров в сетке.
        
    Returns:
        dict[str, any]: Сводка с информацией о сетке.
    """
    if not orders:
        return {}
    
    total_quantity: Decimal = sum(order.quantity for order in orders)
    total_value: Decimal = sum(order.price * order.quantity for order in orders)
    
    prices: List[Decimal] = [order.price for order in orders]
    min_price: Decimal = min(prices)
    max_price: Decimal = max(prices)
    
    return {
        "total_orders": len(orders),
        "total_quantity": total_quantity,
        "total_value": total_value,
        "average_price": total_value / total_quantity if total_quantity > 0 else Decimal('0'),
        "price_range": {
            "min": min_price,
            "max": max_price,
            "spread_percent": float((max_price - min_price) / max_price * 100)
        },
        "market_orders": len([o for o in orders if o.order_type == OrderType.MARKET]),
        "limit_orders": len([o for o in orders if o.order_type == OrderType.LIMIT])
    }
