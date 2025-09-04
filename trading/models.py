from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    """Статусы ордеров"""
    PENDING = "pending"
    PARTIAL_FILLED = "partial_filled"  
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class OrderSide(str, Enum):
    """Стороны ордеров"""
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    """Типы ордеров"""
    MARKET = "market"
    LIMIT = "limit"
    TAKE_PROFIT = "take_profit"

class PositionStatus(str, Enum):
    """Статусы позиций"""
    WAITING = "waiting"
    ACTIVE = "active"    
    CLOSED = "closed"
    ERROR = "error"

class UserStatus(str, Enum):
    """Статусы пользователей"""
    PENDING = "pending"
    SUBSCRIBED = "subscribed"
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING_NEXT = "waiting_next"

class OrderModel(BaseModel):
    """Модель ордера с полной типизацией"""
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
    status: OrderStatus = OrderStatus.PENDING
    grid_level: Optional[int] = None
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    last_check: Optional[datetime] = None
    check_count: int = 0
    error_count: int = 0
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }
        
    @validator('price', 'quantity', 'filled_quantity', pre=True)
    def convert_to_decimal(cls, v):
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v

class TakeProfitModel(BaseModel):
    """Модель тейк-профит ордера"""
    id: Optional[int] = None
    symbol: str
    order_id: str
    price: Decimal
    quantity: Decimal
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }

class UserModel(BaseModel):
    """Модель пользователя"""
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
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat() if v else None
        }

class TradingConfig(BaseModel):
    """Конфигурация торговли"""
    leverage: int = 20
    margin_mode: str = "cross"
    grid_levels: int = 15
    martingale_multiplier: float = 1.3
    coverage_percent: float = 0.4
    take_profit_percent: float = 0.02

class GridOrderData(BaseModel):
    """Данные для построения грид-ордеров"""
    symbol: str
    current_price: Decimal
    deposit_amount: Decimal
    user_id: int
    position_id: int
    
    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }

class OrderStatusUpdate(BaseModel):
    """Модель для обновления статуса ордера"""
    order_id: str
    status: OrderStatus
    filled_quantity: Optional[Decimal] = None
    filled_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: str(v) if v else None,
            datetime: lambda v: v.isoformat() if v else None
        }

class KafkaOrderMessage(BaseModel):
    """Сообщение для Kafka о создании ордера"""
    symbol: str
    order_id: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    quantity: Decimal
    user_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }

class ApiStatsModel(BaseModel):
    """Статистика API"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    last_request_time: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }