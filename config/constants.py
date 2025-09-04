GRID_COVERAGE_PERCENT: float = 0.40  # Перекрытие 40%
GRID_LEVELS: int = 15  # Количество ордеров в сетке
MARTINGALE_MULTIPLIER: float = 1.30  # Мартингейл 30%
TAKE_PROFIT_PERCENT: float = 0.02  # Тейк-профит 2%
LEVERAGE: int = 20  # Плечо
MARGIN_MODE: str = "cross"  # Кросс-маржа
MARKET_ENTRY: bool = True  # Покупаем сразу по маркету

# Временные интервалы
CHECK_DELAY: float = 2.0  # Секунды между проверками ордеров
RESTART_DELAY: int = 60  # Секунды перед перезапуском после тейк-профита

# Список монет в формате ccxt 4.5.3
COINS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT", 
    "BNB/USDT:USDT",
    "ADA/USDT:USDT",
    "SOL/USDT:USDT",
    "MATIC/USDT:USDT",
    "DOT/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "UNI/USDT:USDT"
]