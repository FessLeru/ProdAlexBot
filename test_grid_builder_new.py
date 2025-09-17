#!/usr/bin/env python3
"""
Тестовый файл для демонстрации работы обновленного grid_builder.py
Тестирует различные сценарии с разными депозитами и конфигурациями
"""

from decimal import Decimal, ROUND_DOWN
import logging
from typing import List, Dict, Any

from config.constants import (
    GRID_COVERAGE_PERCENT,
    GRID_LEVELS,
    MARTINGALE_MULTIPLIER,
    TAKE_PROFIT_PERCENT,
    LEVERAGE,
    MARKET_ENTRY
)

from trading.models import TradingConfig
from trading.grid_builder import (
    calculate_total_martingale_multiplier,
    calculate_optimal_base_quantity,
    calculate_martingale_quantities,
    calculate_grid_prices,
    validate_grid_parameters
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def analyze_grid_distribution(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Анализирует распределение грид-сетки для заданного тест-кейса без создания ордеров
    
    Args:
        test_case: Словарь с параметрами теста
        
    Returns:
        Dict[str, Any]: Результаты анализа распределения
    """
    print(f"\n{'='*80}")
    print(f"📊 АНАЛИЗ: {test_case['name']}")
    print(f"{'='*80}")

    deposit: Decimal = Decimal(str(test_case['deposit']))
    price: Decimal = Decimal(str(test_case['current_price']))
    symbol: str = test_case['coin']

    # Создаем конфигурацию торговли
    config = TradingConfig(
        leverage=test_case.get('leverage', LEVERAGE),
        grid_levels=test_case.get('grid_levels', GRID_LEVELS),
        martingale_multiplier=test_case.get('martingale_multiplier', MARTINGALE_MULTIPLIER),
        coverage_percent=test_case.get('coverage_percent', GRID_COVERAGE_PERCENT),
        take_profit_percent=test_case.get('take_profit_percent', TAKE_PROFIT_PERCENT)
    )

    # Валидация параметров
    if not validate_grid_parameters(price, deposit, config):
        print("❌ Ошибка валидации параметров")
        return {}

    # 1. Сначала распределяем сетку по уровням
    print(f"🔧 Распределение сетки по уровням:")
    
    grid_prices: List[Decimal] = calculate_grid_prices(price, config)
    total_multiplier: Decimal = calculate_total_martingale_multiplier(config)
    leverage: Decimal = Decimal(str(config.leverage))
    
    # Рассчитываем базовое количество
    base_quantity: Decimal = calculate_optimal_base_quantity(deposit, price, config)
    quantities: List[Decimal] = calculate_martingale_quantities(base_quantity, config)

    print(f"   📊 Цены грида: {len(grid_prices)} уровней")
    print(f"   🔢 Общий множитель: {total_multiplier:.5f}")
    print(f"   📦 Базовое количество: {base_quantity:.8f}")
    print(f"   📈 Количества с мартингейлом: {len(quantities)} уровней")

    # 2. Рассчитываем маржу для каждого уровня и общую маржу
    print(f"\n💰 Расчет маржи по уровням:")
    
    total_margin: Decimal = Decimal('0')
    total_quantity: Decimal = Decimal('0')
    weighted_price_sum: Decimal = Decimal('0')
    
    order_details: List[Dict[str, Any]] = []
    
    for i, (grid_price, quantity) in enumerate(zip(grid_prices, quantities)):
        # Определяем тип ордера
        order_type: str = "MARKET" if (i == 0 and MARKET_ENTRY) else "LIMIT"
        
        # Рассчитываем параметры для каждого уровня
        order_value: Decimal = grid_price * quantity
        margin_required: Decimal = order_value / leverage
        price_diff_percent: float = float((grid_price - price) / price * 100)
        
        # Суммируем маржу (это и есть общая маржа)
        total_margin += margin_required
        total_quantity += quantity
        weighted_price_sum += grid_price * quantity
        
        order_details.append({
            'level': i,
            'type': order_type,
            'price': float(grid_price),
            'quantity': float(quantity),
            'value_usdt': float(order_value),
            'margin_usdt': float(margin_required),
            'price_diff_percent': price_diff_percent
        })

    # Рассчитываем среднюю цену
    average_price: float = float(weighted_price_sum / total_quantity) if total_quantity > 0 else 0

    # Анализ результатов
    print(f"\n💰 АНАЛИЗ МАРЖИ:")
    print(f"   💵 Запрошенный депозит: {deposit:.2f} USDT")
    print(f"   💵 Общая маржа (сумма всех уровней): {total_margin:.2f} USDT")

    margin_diff: float = float(total_margin) - float(deposit)
    margin_diff_percent: float = abs(margin_diff) / float(deposit) * 100

    print(f"   📊 Разница: {margin_diff:+.2f} USDT ({margin_diff_percent:.1f}%)")
    print(f"   📈 Средняя цена входа: {average_price:.5f}")
    print(f"   📦 Общее количество: {total_quantity:.6f}")

    # Детальная информация по уровням сетки
    print(f"\n📋 РАСПРЕДЕЛЕНИЕ СЕТКИ ПО {len(order_details)} УРОВНЯМ:")
    print(f"{'Lvl':<3} {'Тип':<6} {'Цена':<12} {'Количество':<12} {'Номинал':<10} {'Маржа':<8} {'Отклонение':<10}")
    print(f"{'-'*80}")

    for order_detail in order_details:
        print(f"{order_detail['level']:<3} {order_detail['type']:<6} "
              f"{order_detail['price']:<12.5f} {order_detail['quantity']:<12.6f} "
              f"{order_detail['value_usdt']:<10.2f} {order_detail['margin_usdt']:<8.2f} "
              f"{order_detail['price_diff_percent']:+<10.2f}%")

    return {
        'name': test_case['name'],
        'coin': test_case['coin'],
        'requested_deposit': float(deposit),
        'actual_margin': float(total_margin),
        'difference': margin_diff,
        'difference_percent': margin_diff_percent,
        'first_order_margin': order_details[0]['margin_usdt'],
        'total_multiplier': float(total_multiplier),
        'base_quantity': order_details[0]['quantity'],
        'average_price': average_price,
        'total_orders': len(order_details),
        'market_orders': len([o for o in order_details if o['type'] == 'MARKET']),
        'limit_orders': len([o for o in order_details if o['type'] == 'LIMIT'])
    }

def test_edge_cases() -> None:
    """Тестирует граничные случаи"""
    print(f"\n{'='*80}")
    print(f"🧪 ТЕСТИРОВАНИЕ ГРАНИЧНЫХ СЛУЧАЕВ")
    print(f"{'='*80}")
    
    edge_cases = [
        {
            'name': 'Минимальный депозит',
            'deposit': 1,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Очень маленький депозит',
            'deposit': 0.5,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Высокая цена актива',
            'deposit': 100,
            'coin': 'BTC/USDT:USDT',
            'current_price': 45000
        },
        {
            'name': 'Низкая цена актива',
            'deposit': 50,
            'coin': 'DOGE/USDT:USDT',
            'current_price': 0.08
        }
    ]
    
    for case in edge_cases:
        try:
            result = analyze_grid_distribution(case)
            if result:
                print(f"✅ {case['name']}: Успешно")
            else:
                print(f"❌ {case['name']}: Ошибка валидации")
        except Exception as e:
            print(f"❌ {case['name']}: Исключение - {e}")

def test_different_configurations() -> None:
    """Тестирует различные конфигурации торговли"""
    print(f"\n{'='*80}")
    print(f"⚙️ ТЕСТИРОВАНИЕ РАЗЛИЧНЫХ КОНФИГУРАЦИЙ")
    print(f"{'='*80}")
    
    config_tests = [
        {
            'name': 'Консервативная стратегия',
            'deposit': 100,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78,
            'leverage': 5,
            'grid_levels': 10,
            'martingale_multiplier': 1.1,
            'coverage_percent': 0.2,
            'take_profit_percent': 0.01
        },
        {
            'name': 'Агрессивная стратегия',
            'deposit': 100,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78,
            'leverage': 50,
            'grid_levels': 20,
            'martingale_multiplier': 1.5,
            'coverage_percent': 0.6,
            'take_profit_percent': 0.05
        },
        {
            'name': 'Средняя стратегия',
            'deposit': 100,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78,
            'leverage': 20,
            'grid_levels': 15,
            'martingale_multiplier': 1.3,
            'coverage_percent': 0.4,
            'take_profit_percent': 0.02
        }
    ]
    
    for config_test in config_tests:
        try:
            result = analyze_grid_distribution(config_test)
            if result:
                print(f"✅ {config_test['name']}: Успешно")
            else:
                print(f"❌ {config_test['name']}: Ошибка валидации")
        except Exception as e:
            print(f"❌ {config_test['name']}: Исключение - {e}")

def main() -> None:
    """Основная функция тестирования"""
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ GRID BUILDER")
    print(f"📊 Константы: Плечо={LEVERAGE}x, Уровни={GRID_LEVELS}, Мартингейл={MARTINGALE_MULTIPLIER}x")
    print(f"📈 Покрытие={GRID_COVERAGE_PERCENT*100}%, ТП={TAKE_PROFIT_PERCENT*100}%, MARKET_ENTRY={MARKET_ENTRY}")
    
    # Основные тестовые кейсы с разными депозитами
    main_test_cases = [
        {
            'name': 'Микро депозит',
            'deposit': 3.44,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Малый депозит',
            'deposit': 25,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Средний депозит',
            'deposit': 100,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Большой депозит',
            'deposit': 500,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        },
        {
            'name': 'Очень большой депозит',
            'deposit': 2000,
            'coin': 'CRV/USDT:USDT',
            'current_price': 0.78
        }
    ]

    results: List[Dict[str, Any]] = []
    
    print(f"\n{'='*80}")
    print(f"📊 ОСНОВНЫЕ ТЕСТЫ С РАЗНЫМИ ДЕПОЗИТАМИ")
    print(f"{'='*80}")
    
    for test_case in main_test_cases:
        result = analyze_grid_distribution(test_case)
        if result:
            results.append(result)

    # Сводная таблица результатов
    print(f"\n\n📈 СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print(f"{'='*120}")
    print(f"{'Тест':<20} {'Монета':<15} {'Депозит':<10} {'Факт.маржа':<12} {'Разн.%':<8} "
          f"{'Ср.цена':<10} {'Ордеров':<8} {'Market':<7} {'Limit':<6}")
    print(f"{'-'*120}")

    for result in results:
        print(f"{result['name']:<20} {result['coin']:<15} "
              f"{result['requested_deposit']:<10.0f} {result['actual_margin']:<12.2f} "
              f"{result['difference_percent']:<8.1f}% {result['average_price']:<10.5f} "
              f"{result['total_orders']:<8} {result['market_orders']:<7} {result['limit_orders']:<6}")

    # Тестирование граничных случаев
    test_edge_cases()
    
    # Тестирование различных конфигураций
    test_different_configurations()

    print(f"\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print(f"📊 Протестировано {len(results)} основных сценариев")
    print(f"🧪 + граничные случаи и различные конфигурации")

if __name__ == "__main__":
    main()
