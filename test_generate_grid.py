#!/usr/bin/env python3
"""
Тестовый файл для демонстрации работы grid_builder.py
"""

from decimal import Decimal
import logging

from config.constants import (
    GRID_COVERAGE_PERCENT,
    GRID_LEVELS,
    MARTINGALE_MULTIPLIER,
    TAKE_PROFIT_PERCENT,
    LEVERAGE,
    MARKET_ENTRY,
    MIN_MARKET_ORDER_MARGIN_USDT
)

from trading.models import TradingConfig, OrderModel, OrderSide, OrderType, OrderStatus
from trading.grid_builder import (
    build_grid,
    calculate_total_martingale_multiplier,
    calculate_optimal_base_quantity,
    validate_minimum_market_order,
    adjust_for_minimum_market_order,
    calculate_martingale_quantities,
    get_grid_statistics,
    calculate_grid_prices,
    calculate_take_profit_price,
    create_take_profit_order,
    validate_grid_parameters
)

logging.basicConfig(level=logging.WARNING, format='%(message)s')

def test_grid_calculation(test_case: dict) -> dict:
    """Тестирует расчет грид-сетки для заданного тест-кейса"""
    print(f"\n{'='*80}")
    print(f"📊 ТЕСТ: {test_case['name']}")
    print(f"{'='*80}")

    deposit = Decimal(str(test_case['deposit']))
    price = Decimal(str(test_case['current_price']))
    symbol = test_case['coin']

    config = TradingConfig(
        leverage=LEVERAGE,
        grid_levels=GRID_LEVELS,
        martingale_multiplier=MARTINGALE_MULTIPLIER,
        coverage_percent=GRID_COVERAGE_PERCENT,
        take_profit_percent=TAKE_PROFIT_PERCENT
    )

    # Валидация параметров
    if not validate_grid_parameters(price, deposit, config):
        print("❌ Ошибка валидации параметров")
        return {}

    # Тестируем отдельные функции
    grid_prices = calculate_grid_prices(price, config)
    total_multiplier = calculate_total_martingale_multiplier(config)
    base_quantity = calculate_optimal_base_quantity(deposit, price, config)
    adjusted_quantity = adjust_for_minimum_market_order(deposit, price, config)
    quantities = calculate_martingale_quantities(adjusted_quantity, config)

    print(f"📊 Расчеты:")
    print(f"   Цены грида: {len(grid_prices)} уровней")
    print(f"   Общий множитель: {total_multiplier:.5f}")
    print(f"   Базовое количество: {base_quantity:.8f}")
    print(f"   Скорректированное: {adjusted_quantity:.8f}")

    # Создаем грид-сетку
    orders = build_grid(
        user_id=1,
        position_id=1,
        symbol=symbol,
        current_price=price,
        deposit_amount=deposit,
        config=config
    )

    # Получаем статистику
    stats = get_grid_statistics(orders, config)
    
    # Тестируем тейк-профит функции
    average_price = stats['summary']['average_price']
    total_quantity = stats['summary']['total_quantity']
    take_profit_price = calculate_take_profit_price(Decimal(str(average_price)), config)
    take_profit_order = create_take_profit_order(
        user_id=1,
        position_id=1,
        symbol=symbol,
        average_price=Decimal(str(average_price)),
        total_quantity=Decimal(str(total_quantity)),
        config=config
    )

    print(f"\n💰 ИТОГОВАЯ МАРЖА:")
    print(f"   Запрошенная: {deposit:.2f} USDT")
    print(f"   Фактическая: {stats['summary']['total_margin_usdt']:.2f} USDT")

    margin_diff = stats['summary']['total_margin_usdt'] - float(deposit)
    margin_diff_percent = abs(margin_diff) / float(deposit) * 100

    print(f"   Разница: {margin_diff:+.2f} USDT ({margin_diff_percent:.1f}%)")

    print(f"\n🎯 ТЕЙК-ПРОФИТ:")
    print(f"   Средняя цена: {average_price:.5f}")
    print(f"   Цена ТП: {take_profit_price:.5f}")
    print(f"   Количество ТП: {total_quantity:.6f}")
    print(f"   Прибыль: {((take_profit_price - Decimal(str(average_price))) / Decimal(str(average_price)) * 100):.2f}%")

    print(f"\n📋 ВСЕ {len(stats['order_details'])} ОРДЕРОВ:")
    print(f"{'Lvl':<3} {'Тип':<6} {'Цена':<12} {'Количество':<12} {'Номинал':<10} {'Маржа':<8} {'Отклонение':<10}")
    print(f"{'-'*80}")

    for order_detail in stats['order_details']:
        print(f"{order_detail['level']:<3} {order_detail['type']:<6} "
              f"{order_detail['price']:<12.5f} {order_detail['quantity']:<12.6f} "
              f"{order_detail['value_usdt']:<10.2f} {order_detail['margin_usdt']:<8.2f} "
              f"{order_detail['price_diff_percent']:+<10.2f}%")

    return {
        'name': test_case['name'],
        'coin': test_case['coin'],
        'requested_deposit': float(deposit),
        'actual_margin': stats['summary']['total_margin_usdt'],
        'difference': margin_diff,
        'difference_percent': margin_diff_percent,
        'first_order_margin': stats['order_details'][0]['margin_usdt'],
        'min_check_passed': stats['validation']['margin_check_passed'],
        'total_multiplier': float(total_multiplier),
        'base_quantity': stats['order_details'][0]['quantity'],
        'take_profit_price': float(take_profit_price),
        'average_price': average_price,
        'profit_percent': float((take_profit_price - Decimal(str(average_price))) / Decimal(str(average_price)) * 100)
    }

def main() -> None:
    """Основная функция тестирования"""
    # Тестовые кейсы с понятной структурой
    test_cases = [
        {
            'name': 'Малый депозит CRV',
            'deposit': 10,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Средний депозит CRV',
            'deposit': 30,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Большой депозит CRV',
            'deposit': 1000,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        }
    ]

    results = []
    for test_case in test_cases:
        result = test_grid_calculation(test_case)
        results.append(result)

    # Сводная таблица результатов
    print(f"\n\n📈 СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print(f"{'='*120}")
    print(f"{'Тест':<20} {'Монета':<15} {'Депозит':<10} {'Факт.маржа':<12} {'Разн.%':<8} {'ТП цена':<10} {'Прибыль%':<10} {'Мин.чек':<8}")
    print(f"{'-'*120}")

    for result in results:
        status = "✅" if result['min_check_passed'] else "❌"
        print(f"{result['name']:<20} {result['coin']:<15} "
              f"{result['requested_deposit']:<10.0f} {result['actual_margin']:<12.2f} "
              f"{result['difference_percent']:<8.1f}% {result['take_profit_price']:<10.5f} "
              f"{result['profit_percent']:<10.2f}% {status:<8}")

    print(f"\n✅ Тестирование завершено!")

if __name__ == "__main__":
    main()