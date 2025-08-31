from typing import List
import os
import dotenv

dotenv.load_dotenv()

class Settings:
    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_TELEGRAM_IDS: List[int] = []
    
    # Database
    DATABASE_PATH: str = "database.db"
    
    # Bitget API
    BITGET_API_URL: str = "https://api.bitget.com"
    TRADER_ID: str = os.getenv("TRADER_ID")
    TRADER_API_KEY: str = os.getenv("TRADER_API_KEY")
    TRADER_API_SECRET: str = os.getenv("TRADER_API_SECRET")
    TRADER_API_PASSPHRASE: str = os.getenv("TRADER_API_PASSPHRASE")
    
    TRADING_START_DELAY: int = 300  # 5 минут в секундах
    
    # Encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    
    # Trading
    MAX_ACTIVE_POSITIONS: int = 15
    ORDER_CHECK_INTERVAL: float = 2.0  # секунды между проверками
    BATCH_ORDER_SIZE: int = 5  # количество ордеров в одном запросе
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_WINDOW: int = 60
    MAX_CONCURRENT_REQUESTS: int = 5
    
    class Config:
        env_file = ".env"

settings = Settings()
