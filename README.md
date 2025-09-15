# 🚀 BotFeature - Автоматический торговый бот для Bitget

## 📋 Обзор проекта

**BotFeature** - это комплексная система для автоматической торговли криптовалютами на бирже Bitget, использующая стратегию грид-торговли (grid trading) с мартингейл-эффектом и плечом 20x.

### Ключевые особенности:
- ✅ **Grid Trading** - сетевая торговля с 15 уровнями ордеров
- ✅ **Мартингейл** - увеличение объема на каждом уровне на 30%
- ✅ **Плечо 20x** - максимизация прибыли с контролем риска
- ✅ **Автоматический тейк-профит** - продажа с прибылью 2%
- ✅ **Telegram бот** - удобное управление через мессенджер
- ✅ **Асинхронная обработка** - высокая производительность через Celery
- ✅ **Мониторинг в реальном времени** - отслеживание ордеров каждые 2 секунды

## 💰 Что такое deposit_amount и расчет реальных средств

### deposit_amount - базовый депозит на одну монету

```python
# В main.py установлено значение по умолчанию
deposit_per_coin = 10.0  # USDT на каждую монету
```

### 📊 Расчет реальных средств с плечом 20x

**ВАЖНО**: `deposit_amount` - это ваш РЕАЛЬНЫЙ депозит в USDT, который будет заблокирован как маржа.

#### Пример расчета:
- **deposit_amount = 10 USDT** (ваши реальные деньги)
- **Плечо = 20x**
- **Торговый капитал = 10 USDT × 20 = 200 USDT** (виртуальный объем для торговли)

#### Детальный разбор на примере монеты CRV/USDT:

```python
# При deposit_amount = 10 USDT:
Реальный депозит: 10 USDT (ваши средства)
Торговый капитал с плечом: 10 × 20 = 200 USDT
Покрытие сетки: 200 × 0.40 = 80 USDT диапазон цен
Количество уровней: 15 ордеров
Мартингейл: каждый следующий ордер больше на 30%
```

#### Расчет размера ордеров в грид-сетке:

```python
def calculate_optimal_base_quantity(deposit_amount, current_price, config):
    # Доступная сумма с плечом
    available_amount = deposit_amount * leverage  # 10 * 20 = 200 USDT
    
    # Расчет общего множителя для мартингейла
    # Уровень 1: 1.0
    # Уровень 2: 1.3
    # Уровень 3: 1.69
    # ... и так далее до 15 уровня
    total_multiplier = сумма_всех_мультипликаторов  # ≈ 142.8
    
    # Базовое количество для первого ордера
    base_quantity = available_amount / (total_multiplier * current_price)
```

### 💡 Практический пример:

При цене CRV = $0.50 и deposit_amount = 10 USDT:

```
Реальные средства: 10 USDT
Торговый объем: 200 USDT
Базовый ордер: ~0.28 USDT (≈ 0.56 CRV)
Самый большой ордер (15 уровень): ~10.2 USDT (≈ 20.4 CRV)
Общий объем всех ордеров: 200 USDT
```

### ⚠️ ВАЖНЫЕ МОМЕНТЫ ПО ДЕПОЗИТУ:

1. **Минимальный депозит**: Рекомендуется минимум 5 USDT на монету
2. **Риск ликвидации**: При сильном падении цены более чем на 40% возможна ликвидация
3. **Свободные средства**: Держите на счету дополнительные средства для покрытия возможных просадок
4. **Расчет на все монеты**: Если торгуете 5 монетами с deposit_amount = 10, нужно минимум 50 USDT

## 🏗️ Архитектура системы

### Основные компоненты:

```
├── 🤖 Telegram Bot (telegram/)
│   ├── bot.py - главный модуль бота
│   ├── handlers/ - обработчики команд
│   └── keyboards/ - клавиатуры интерфейса
│
├── 📈 Trading Engine (trading/)
│   ├── grid_builder.py - построение торговых сеток
│   ├── order_tracker.py - отслеживание ордеров
│   └── celery_worker.py - асинхронная обработка
│
├── 🔌 API Integration (api/)
│   └── bybit_api.py - интеграция с Bybit API
│
├── 💾 Database (database/)
│   ├── connection.py - подключение к SQLite
│   ├── repositories/ - репозитории данных
│   └── schema.sql - схема базы данных
│
├── ⚙️ Configuration (config/)
│   ├── settings.py - настройки системы
│   └── constants.py - торговые константы
│
└── 🛠️ Utils (utils/)
    ├── encryption.py - шифрование API ключей
    ├── logger.py - система логирования
    └── rate_limiter.py - ограничение запросов
```

### Поток данных:
```
1. main.py → Запуск системы
2. Celery Worker → Создание торговых задач для каждой монеты
3. OrderTracker → Построение грид-сетки ордеров
4. BybitAPI → Размещение ордеров на бирже
5. Database → Сохранение информации об ордерах
6. Kafka → Уведомления о торговых событиях
7. Telegram Bot → Получение уведомлений администратором
```

## 📦 Установка и настройка

### 1. Системные требования:
- Python 3.12+
- Redis server
- SQLite3

### 2. Установка зависимостей:
```bash
# Клонируем репозиторий
git clone <repository-url>
cd BotFeauture

# Создаем виртуальное окружение
python -m venv venv

# Активируем окружение
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 3. Настройка переменных окружения:

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=123456789,987654321
ADMIN_CHAT_ID=your_chat_id

# Bybit API (получить на https://www.bybit.com/app/user/api-management)
TRADER_API_KEY=your_api_key
TRADER_API_SECRET=your_api_secret

# Генерируем ключ шифрования
python generate_encryption_key.py
# Копируем сгенерированный ключ в .env:
ENCRYPTION_KEY=your_generated_encryption_key

# Redis (по умолчанию)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Kafka (опционально)
KAFKA_SERVERS=localhost:9092
```

### 4. Настройка торговых параметров:

В файле `config/constants.py`:

```python
# Торговые настройки
GRID_COVERAGE_PERCENT: float = 0.40    # Покрытие 40% от текущей цены
GRID_LEVELS: int = 15                   # 15 ордеров в сетке
MARTINGALE_MULTIPLIER: float = 1.30     # Увеличение на 30% каждый уровень
TAKE_PROFIT_PERCENT: float = 0.02       # Тейк-профит 2%
LEVERAGE: int = 20                      # Плечо 20x
MARGIN_MODE: str = "cross"              # Кросс-маржа

# Временные интервалы
CHECK_DELAY: float = 2.0                # Проверка ордеров каждые 2 сек
RESTART_DELAY: int = 60                 # Пауза 60 сек после тейк-профита

# Торгуемые монеты
COINS = [
    "CRV/USDT:USDT",
    # Добавьте другие монеты по желанию
    # "ARB/USDT:USDT",
    # "OP/USDT:USDT",
]
```

### 5. Настройка депозита:

В файле `main.py`:

```python
def start_trading() -> None:
    # Указываем депозит на каждую монету в USDT
    deposit_per_coin = 10.0  # Измените на желаемую сумму
    
    start_master_trading.delay(
        api_key=settings.TRADER_API_KEY,
        api_secret=settings.TRADER_API_SECRET, 
        deposit_per_coin=deposit_per_coin
    )
```

## 🚀 Запуск проекта

### Способ 1: Полная система (бот + торговля)

```bash
# 1. Запустите Redis server
redis-server

# 2. В новом терминале запустите Celery worker
celery -A trading.celery_worker worker --loglevel=info

# 3. В третьем терминале запустите основную систему
python main.py
```

### Способ 2: Только торговля (без Telegram бота)

```bash
# 1. Запустите Redis server
redis-server

# 2. В новом терминале запустите Celery worker  
celery -A trading.celery_worker worker --loglevel=info

# 3. В третьем терминале запустите только торговлю
python run_trading_only.py
```

### Способ 3: Docker (рекомендуется для production)

```bash
# Запуск всех сервисов через Docker Compose
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка системы
docker-compose down
```

## 📊 Торговая стратегия

### Grid Trading с мартингейлом:

1. **Построение сетки**: Создается 15 ордеров на покупку ниже текущей цены
2. **Распределение цен**: Ордера распределяются равномерно в диапазоне 40% от текущей цены
3. **Мартингейл**: Каждый следующий ордер больше предыдущего на 30%
4. **Первый ордер**: Покупается сразу по рыночной цене (если `MARKET_ENTRY = True`)
5. **Отслеживание**: Каждые 2 секунды проверяется статус всех ордеров
6. **Тейк-профит**: При исполнении любого ордера создается ордер на продажу с прибылью 2%
7. **Перезапуск**: После исполнения тейк-профита система ждет 60 секунд и создает новую сетку

### Пример работы стратегии:

```
Текущая цена CRV: $0.50
Депозит: 10 USDT (200 USDT с плечом 20x)

Грид-сетка:
├── Market: $0.50 - 0.56 CRV (~0.28 USDT)
├── Level 1: $0.487 - 0.75 CRV (~0.36 USDT) 
├── Level 2: $0.475 - 0.97 CRV (~0.46 USDT)
├── Level 3: $0.462 - 1.26 CRV (~0.58 USDT)
├── ...
└── Level 14: $0.300 - 68.0 CRV (~20.4 USDT)

При падении цены до $0.450:
✅ Исполнится Level 1 и Level 2
✅ Создастся тейк-профит на продажу 1.72 CRV по цене $0.459 (+2%)
✅ При достижении тейк-профита = прибыль ~1.54%
✅ Через 60 секунд создается новая сетка
```

## 🔧 Конфигурация и настройки

### Основные файлы настроек:

#### `config/settings.py`:
- API ключи и секреты
- Настройки баз данных
- Лимиты запросов
- Конфигурация Redis и Celery

#### `config/constants.py`:
- Торговые параметры стратегии
- Список торгуемых монет
- Интервалы проверок

### Настройка безопасности:

```python
# Шифрование API ключей в базе данных
from utils.encryption import encrypt_data, decrypt_data

# Зашифровать данные
encrypted_key = encrypt_data("your_api_key")

# Расшифровать данные  
decrypted_key = decrypt_data(encrypted_key)
```

## 📁 База данных

### Схема таблиц:

#### `users` - Пользователи системы:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    api_key_encrypted TEXT,        -- Зашифрованный API ключ
    api_secret_encrypted TEXT,     -- Зашифрованный API секрет
    deposit_amount DECIMAL(10,2),  -- Размер депозита
    status TEXT DEFAULT 'pending', -- Статус пользователя
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `limit_orders` - Лимитные ордера:
```sql
CREATE TABLE limit_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,              -- Торговая пара (например, CRV/USDT:USDT)
    order_id TEXT UNIQUE NOT NULL,     -- ID ордера на бирже
    price DECIMAL(18,8) NOT NULL,      -- Цена ордера
    quantity DECIMAL(18,8) NOT NULL,   -- Количество
    filled_quantity DECIMAL(18,8),     -- Исполненное количество
    status TEXT DEFAULT 'pending',     -- Статус: pending/filled/cancelled
    grid_level INTEGER,                -- Уровень в сетке (0-14)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filled_at DATETIME                 -- Время исполнения
);
```

#### `take_profit_orders` - Тейк-профит ордера:
```sql
CREATE TABLE take_profit_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    order_id TEXT UNIQUE NOT NULL,
    price DECIMAL(18,8) NOT NULL,      -- Цена тейк-профита (+2% от средней)
    quantity DECIMAL(18,8) NOT NULL,   -- Общее количество к продаже
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filled_at DATETIME
);
```

## 🔌 API интеграция

### Bybit API:

Система использует официальную библиотеку `ccxt` для взаимодействия с биржей Bybit:

```python
class BybitAPI:
    def __init__(self, api_key, api_secret):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'sandbox': False,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Фьючерсная торговля
            }
        })
```

### Основные API методы:

- `get_ticker_price()` - получение текущей цены
- `create_market_order()` - создание рыночного ордера
- `create_limit_order()` - создание лимитного ордера
- `fetch_order()` - получение информации об ордере
- `cancel_order()` - отмена ордера
- `set_leverage()` - установка плеча
- `get_account_balance()` - получение баланса

### Rate Limiting:

Система имеет встроенную защиту от превышения лимитов API:

```python
class RateLimiter:
    def __init__(self):
        self.max_requests = 100      # Максимум запросов
        self.window = 60             # За 60 секунд
        self.max_concurrent = 5      # Одновременно
```

## 📱 Telegram интеграция

### Основные возможности бота:

- 📊 Просмотр статуса торговли
- 🔧 Управление настройками
- 📈 Получение уведомлений о сделках
- ⚡ Быстрые команды управления

### Система уведомлений:

```python
# Уведомления через Kafka
async def _send_order_notification(order):
    message = {
        'symbol': order.symbol,
        'order_id': order.order_id,
        'side': order.side,
        'price': order.price,
        'quantity': order.quantity
    }
    await kafka_producer.send('trading_notifications', message)
```

## 🔄 Celery задачи

### Архитектура задач:

```
start_master_trading
├── start_symbol_trading (для каждой монеты)
│   ├── Построение грид-сетки
│   ├── Размещение ордеров
│   └── track_symbol_continuously
│       ├── Проверка статуса ордеров
│       ├── Обновление тейк-профита
│       └── restart_symbol_after_delay (при срабатывании ТП)
```

### Мониторинг задач:

```bash
# Просмотр активных задач
celery -A trading.celery_worker inspect active

# Статистика воркеров
celery -A trading.celery_worker inspect stats

# Остановка всех задач торговли
celery -A trading.celery_worker call stop_all_trading
```

## 📈 Мониторинг и логирование

### Система логирования:

```python
# Уровни логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Примеры логов:
🚀 Запуск торговли для CRV/USDT:USDT
✅ Размещен ордер limit_123 buy 1.5 CRV/USDT:USDT @ 0.487
🎯 Обновлен тейк-профит CRV/USDT:USDT: 0.499 x 2.3
🔄 Планируем перезапуск CRV/USDT:USDT через 60 сек
```

### Мониторинг производительности:

- **Redis**: Хранение временных данных и очереди задач
- **SQLite**: База данных ордеров и пользователей  
- **Rate Limiting**: Контроль частоты API запросов
- **Health Checks**: Проверка состояния компонентов

## ⚠️ Риски и рекомендации

### Основные риски:

1. **Риск ликвидации**: При резком падении > 40% возможна ликвидация позиции
2. **Боковой тренд**: Стратегия работает лучше в боковом движении
3. **Сильный нисходящий тренд**: Может привести к большим просадкам
4. **API лимиты**: Превышение лимитов может привести к блокировке

### Рекомендации по безопасности:

1. **Начинайте с малых сумм** - тестируйте на минимальных депозитах
2. **Диверсифицируйте риски** - торгуйте разными монетами
3. **Мониторьте рынок** - следите за новостями и трендами
4. **Держите резерв** - дополнительные средства на счету для покрытия просадок
5. **Регулярно проверяйте** - контролируйте работу системы
6. **Используйте стоп-лоссы** - рассмотрите добавление защитных механизмов

### Настройка для разных уровней риска:

#### 🔴 Высокий риск / Высокая доходность:
```python
GRID_COVERAGE_PERCENT = 0.50    # Покрытие 50%
LEVERAGE = 20                   # Максимальное плечо
TAKE_PROFIT_PERCENT = 0.015     # ТП 1.5%
deposit_per_coin = 5.0          # Минимальный депозит
```

#### 🟡 Средний риск / Сбалансированный:
```python
GRID_COVERAGE_PERCENT = 0.40    # Покрытие 40% (по умолчанию)
LEVERAGE = 15                   # Умеренное плечо
TAKE_PROFIT_PERCENT = 0.02      # ТП 2%  
deposit_per_coin = 10.0         # Рекомендуемый депозит
```

#### 🟢 Низкий риск / Консервативный:
```python
GRID_COVERAGE_PERCENT = 0.30    # Покрытие 30%
LEVERAGE = 10                   # Низкое плечо
TAKE_PROFIT_PERCENT = 0.025     # ТП 2.5%
deposit_per_coin = 20.0         # Увеличенный депозит
```

## 🛠️ Разработка и кастомизация

### Добавление новых монет:

В файле `config/constants.py`:
```python
COINS = [
    "CRV/USDT:USDT",
    "ARB/USDT:USDT",     # Добавьте новую монету
    "OP/USDT:USDT",      # Еще одну монету
    # Проверьте доступность на Bitget
]
```

### Кастомизация стратегии:

Создайте собственную конфигурацию:
```python
custom_config = TradingConfig(
    leverage=25,                    # Свое плечо
    grid_levels=20,                # Больше уровней
    martingale_multiplier=1.2,     # Меньший мартингейл
    coverage_percent=0.6,          # Больший диапазон
    take_profit_percent=0.015      # Меньший ТП
)
```

### Расширение функциональности:

1. **Добавление индикаторов** - интегрируйте технический анализ
2. **Умные стоп-лоссы** - защита от больших просадок  
3. **Динамические параметры** - адаптация к волатильности
4. **Множественные стратегии** - разные подходы для разных монет
5. **Бэктестинг** - тестирование на исторических данных

## 📞 Поддержка и контакты

### В случае проблем:

1. **Проверьте логи** - основная информация об ошибках
2. **Проверьте API ключи** - корректность и права доступа
3. **Проверьте баланс** - достаточность средств на счету
4. **Проверьте соединение** - доступность Redis и интернета

### Полезные команды для диагностики:

```bash
# Проверка статуса Redis
redis-cli ping

# Проверка активных задач Celery
celery -A trading.celery_worker inspect active

# Тест API соединения
python -c "from api.bybit_api import BybitAPI; import asyncio; api = BybitAPI('key', 'secret'); print(asyncio.run(api.test_connection()))"

# Проверка базы данных
sqlite3 database.db ".tables"
```

---

## 🎯 Заключение

**BotFeature** - это мощная система автоматической торговли, которая при правильной настройке и управлении рисками может приносить стабильную прибыль. Помните, что торговля криптовалютами всегда связана с рисками, поэтому:

- 📚 **Изучайте рынок** перед началом торговли
- 💰 **Не инвестируйте больше**, чем можете позволить себе потерять  
- 📊 **Тестируйте на демо-счете** или малых суммах
- 🔄 **Постоянно мониторьте** работу системы
- 📈 **Анализируйте результаты** и оптимизируйте параметры

Удачной торговли! 🚀

---

*Документация обновлена: Январь 2024*
*Версия проекта: 1.0.0*
*Python версия: 3.12+*
