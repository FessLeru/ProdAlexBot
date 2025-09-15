-- Пользователи
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    status TEXT DEFAULT 'pending',
    deposit_amount DECIMAL(10,2) DEFAULT 0,
    is_following_trader BOOLEAN DEFAULT FALSE,
    subscription_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Таблица лимитных ордеров
CREATE TABLE IF NOT EXISTS limit_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    order_id TEXT UNIQUE NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    filled_quantity DECIMAL(18,8) DEFAULT 0,
    status TEXT DEFAULT 'pending',
    grid_level INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filled_at DATETIME
);

-- Таблица тейк-профит ордеров
CREATE TABLE IF NOT EXISTS take_profit_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    order_id TEXT UNIQUE NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    filled_at DATETIME
);