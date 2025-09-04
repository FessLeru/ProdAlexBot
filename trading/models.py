from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIAL_FILLED = "partial_filled"  
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    TAKE_PROFIT = "take_profit"

class PositionStatus(str, Enum):
    WAITING = "waiting"  # Ждет начала торговли
    ACTIVE = "active"    # Активная позиция
    CLOSED = "closed"    # Закрытая позиция
    ERROR = "error"      # Ошибка

class UserStatus(str, Enum):
    PENDING = "pending"          # Ожидает начала торговли
    SUBSCRIBED = "subscribed"    # Подписан на трейдера
    ACTIVE = "active"           # Активно торгует
    PAUSED = "paused"           # Торговля приостановлена
    WAITING_NEXT = "waiting_next"  # Ждет следующего цикла

class TradingConfig(BaseModel):
    leverage: int = 20
    margin_mode: str = "cross"
    grid_levels: int = 15
    martingale_multiplier: float = 1.3
    coverage_percent: float = 0.4
    take_profit_percent: float = 0.02

class UserAPIKeysModel(BaseModel):
    api_key: str
    api_secret: str
    api_passphrase: str
    
    @validator('*', pre=True)
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('API ключи не могут быть пустыми')
        return v.strip()

class OrderModel(BaseModel):
    id: Optional[int] = None
    user_id: int
    position_id: int
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal = Decimal('0')
    status: OrderStatus
    grid_level: Optional[int] = None
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    last_check: Optional[datetime] = None
    check_count: int = 0
    error_count: int = 0


class UserModel(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    api_key_encrypted: Optional[str] = None
    api_secret_encrypted: Optional[str] = None
    api_passphrase_encrypted: Optional[str] = None
    status: UserStatus = UserStatus.PENDING
    deposit_amount: Decimal = Decimal('0')
    is_following_trader: bool = False
    subscription_time: Optional[datetime] = None
    created_at: Optional[datetime] = None