from decimal import Decimal

GRID_COVERAGE_PERCENT: float = 0.40  # Перекрытие 40%
GRID_LEVELS: int = 15  # Количество ордеров в сетке
MARTINGALE_MULTIPLIER: float = 1.30  # Мартингейл 30%
TAKE_PROFIT_PERCENT: float = 0.02  # Тейк-профит 2%
LEVERAGE: int = 20  # Плечо
MARGIN_MODE: str = "cross"  # Кросс-маржа
MARKET_ENTRY: bool = True  # Покупаем сразу по маркету

# Временные интервалы
CHECK_DELAY: float = 1.0  # Секунды между проверками ордеров (уменьшено для быстрого реагирования)
RESTART_DELAY: int = 30  # Секунды перед перезапуском после тейк-профита (уменьшено)

# Список монет в формате ccxt 4.5.3
COINS = [
    "JASMY/USDT:USDT",
    "GRT/USDT:USDT",
    "GALA/USDT:USDT",
    # "WLD/USDT:USDT",
    #"CRV/USDT:USDT",
    "THETA/USDT:USDT",
    "SXP/USDT:USDT",
    # "APT/USDT:USDT",
    # "APE/USDT:USDT",
    "ALGO/USDT:USDT"
]