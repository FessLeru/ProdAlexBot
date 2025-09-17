import os
from typing import List
import dotenv

dotenv.load_dotenv()

class Settings:
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    ADMIN_TELEGRAM_IDS: List[int] = [
        int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x
    ]
    ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID")
    
    # Database
    DATABASE_PATH: str = "database.db"
    
    # Bybit API
    BYBIT_API_URL: str = "https://api.bybit.com"
    TRADER_API_KEY: str = os.getenv("TRADER_API_KEY")
    TRADER_API_SECRET: str = os.getenv("TRADER_API_SECRET")
    TRADER_ID: str = os.getenv("TRADER_ID")
    
    TRADING_START_DELAY: int = 300  # 5 минут в секундах
    
    # Encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    
    # Trading
    MAX_ACTIVE_POSITIONS: int = 15
    ORDER_CHECK_INTERVAL: float = 2.0  # секунды между проверками
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 50  # Уменьшено для fake user agent
    RATE_LIMIT_WINDOW: int = 60
    MAX_CONCURRENT_REQUESTS: int = 3  # Уменьшено
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # Kafka
    KAFKA_SERVERS: List[str] = os.getenv("KAFKA_SERVERS", "localhost:9092").split(",")
    KAFKA_TOPIC_NOTIFICATIONS: str = "trading_notifications"
    
    class Config:
        env_file = ".env"

settings = Settings()