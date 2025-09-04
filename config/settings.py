from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Класс настроек приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_TELEGRAM_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x]
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "database.db")
    
    # Bitget API
    BITGET_API_URL: str = "https://api.bitget.com"
    TRADER_API_KEY: str = os.getenv("TRADER_API_KEY", "")
    TRADER_API_SECRET: str = os.getenv("TRADER_API_SECRET", "")
    TRADER_API_PASSPHRASE: str = os.getenv("TRADER_API_PASSPHRASE", "")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # Encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # Trading
    MAX_ACTIVE_POSITIONS: int = int(os.getenv("MAX_ACTIVE_POSITIONS", "15"))
    TRADING_START_DELAY: int = int(os.getenv("TRADING_START_DELAY", "60"))
    
    # Rate Limiting (уменьшено из-за fake user agent)
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "50"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
    
    # Kafka для уведомлений
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_ORDERS_TOPIC: str = os.getenv("KAFKA_ORDERS_TOPIC", "trading_orders")

settings = Settings()