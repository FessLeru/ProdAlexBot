"""
Репозиторий для работы с пользователями в базе данных.
Содержит методы для создания, обновления и получения информации о пользователях.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from database.connection import DatabaseConnection
from trading.models import UserModel, UserStatus


class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def create(self, user: UserModel) -> int:
        """
        Создание нового пользователя.
        
        Args:
            user: Модель пользователя
            
        Returns:
            int: ID созданного пользователя
        """
        query = """
            INSERT INTO users (
                telegram_id, username, first_name, api_key_encrypted,
                api_secret_encrypted, api_passphrase_encrypted, status,
                deposit_amount, is_following_trader, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            user.telegram_id,
            user.username,
            user.first_name,
            user.api_key_encrypted,
            user.api_secret_encrypted,
            user.api_passphrase_encrypted,
            user.status.value,
            float(user.deposit_amount),
            user.is_following_trader,
            user.created_at.isoformat() if user.created_at else datetime.utcnow().isoformat()
        )
        
        return await self.db.execute_write(query, params)

    async def get_by_id(self, user_id: int) -> Optional[UserModel]:
        """
        Получение пользователя по ID.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Optional[UserModel]: Модель пользователя или None
        """
        query = "SELECT * FROM users WHERE id = ?"
        row = await self.db.execute_single(query, (user_id,))
        
        return self._row_to_user_model(row) if row else None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserModel]:
        """
        Получение пользователя по Telegram ID.
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Optional[UserModel]: Модель пользователя или None
        """
        query = "SELECT * FROM users WHERE telegram_id = ?"
        row = await self.db.execute_single(query, (telegram_id,))
        
        return self._row_to_user_model(row) if row else None

    async def update_api_keys(
        self,
        user_id: int,
        api_key_encrypted: str,
        api_secret_encrypted: str,
        api_passphrase_encrypted: str
    ) -> None:
        """
        Обновление API ключей пользователя.
        
        Args:
            user_id: ID пользователя
            api_key_encrypted: Зашифрованный API ключ
            api_secret_encrypted: Зашифрованный API секрет
            api_passphrase_encrypted: Зашифрованная API фраза
        """
        query = """
            UPDATE users 
            SET api_key_encrypted = ?, api_secret_encrypted = ?, 
                api_passphrase_encrypted = ?, updated_at = ?
            WHERE id = ?
        """
        
        params = (
            api_key_encrypted,
            api_secret_encrypted,
            api_passphrase_encrypted,
            datetime.utcnow().isoformat(),
            user_id
        )
        
        await self.db.execute_write(query, params)

    async def update_user_status(
        self,
        user_id: int,
        status: UserStatus,
        is_following: Optional[bool] = None,
        subscription_time: Optional[datetime] = None,
        deposit_amount: Optional[Decimal] = None
    ) -> None:
        """
        Обновление статуса пользователя.
        
        Args:
            user_id: ID пользователя
            status: Новый статус
            is_following: Флаг подписки на трейдера
            subscription_time: Время подписки
            deposit_amount: Сумма депозита
        """
        # Базовые поля для обновления
        set_clauses = ["status = ?", "updated_at = ?"]
        params = [status.value, datetime.utcnow().isoformat()]
        
        # Добавляем опциональные поля
        if is_following is not None:
            set_clauses.append("is_following_trader = ?")
            params.append(is_following)
            
        if subscription_time is not None:
            set_clauses.append("subscription_time = ?")
            params.append(subscription_time.isoformat())
            
        if deposit_amount is not None:
            set_clauses.append("deposit_amount = ?")
            params.append(float(deposit_amount))
        
        # Добавляем WHERE условие
        params.append(user_id)
        
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        await self.db.execute_write(query, params)

    async def get_following_users(self) -> List[UserModel]:
        """
        Получение всех пользователей, подписанных на трейдера.
        
        Returns:
            List[UserModel]: Список подписанных пользователей
        """
        query = """
            SELECT * FROM users 
            WHERE is_following_trader = TRUE AND status IN ('subscribed', 'active')
            ORDER BY subscription_time ASC
        """
        
        rows = await self.db.execute_query(query)
        return [self._row_to_user_model(row) for row in rows]

    async def get_active_users(self) -> List[UserModel]:
        """
        Получение всех активных пользователей.
        
        Returns:
            List[UserModel]: Список активных пользователей
        """
        query = """
            SELECT * FROM users 
            WHERE status = 'active'
            ORDER BY created_at ASC
        """
        
        rows = await self.db.execute_query(query)
        return [self._row_to_user_model(row) for row in rows]

    async def update_deposit_amount(self, user_id: int, amount: Decimal) -> None:
        """
        Обновление суммы депозита пользователя.
        
        Args:
            user_id: ID пользователя
            amount: Новая сумма депозита
        """
        query = """
            UPDATE users 
            SET deposit_amount = ?, updated_at = ?
            WHERE id = ?
        """
        
        params = (float(amount), datetime.utcnow().isoformat(), user_id)
        await self.db.execute_write(query, params)

    async def delete_user(self, user_id: int) -> None:
        """
        Удаление пользователя.
        
        Args:
            user_id: ID пользователя
        """
        query = "DELETE FROM users WHERE id = ?"
        await self.db.execute_write(query, (user_id,))

    async def get_user_statistics(self) -> dict:
        """
        Получение статистики по пользователям.
        
        Returns:
            dict: Статистика пользователей
        """
        queries = {
            'total_users': "SELECT COUNT(*) as count FROM users",
            'active_users': "SELECT COUNT(*) as count FROM users WHERE status = 'active'",
            'following_users': "SELECT COUNT(*) as count FROM users WHERE is_following_trader = TRUE",
            'pending_users': "SELECT COUNT(*) as count FROM users WHERE status = 'pending'"
        }
        
        stats = {}
        for key, query in queries.items():
            result = await self.db.execute_single(query)
            stats[key] = result['count'] if result else 0
            
        return stats

    def _row_to_user_model(self, row) -> UserModel:
        """
        Преобразование строки БД в модель пользователя.
        
        Args:
            row: Строка из базы данных
            
        Returns:
            UserModel: Модель пользователя
        """
        return UserModel(
            id=row['id'],
            telegram_id=row['telegram_id'],
            username=row['username'],
            first_name=row['first_name'],
            api_key_encrypted=row['api_key_encrypted'],
            api_secret_encrypted=row['api_secret_encrypted'],
            api_passphrase_encrypted=row['api_passphrase_encrypted'],
            status=UserStatus(row['status']),
            deposit_amount=Decimal(str(row['deposit_amount'])),
            is_following_trader=bool(row['is_following_trader']),
            subscription_time=(
                datetime.fromisoformat(row['subscription_time']) 
                if row['subscription_time'] else None
            ),
            created_at=(
                datetime.fromisoformat(row['created_at']) 
                if row['created_at'] else None
            )
        )
