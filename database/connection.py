import aiosqlite
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    _instance: Optional['DatabaseConnection'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path = settings.DATABASE_PATH
            self.connection_pool = []
            self.pool_size = 10
            self.initialized = True
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Читаем схему из файла
            with open('database/schema.sql', 'r', encoding='utf-8') as f:
                schema = f.read()
            
            await db.executescript(schema)
            await db.commit()
            
        logger.info("База данных инициализирована")
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения с базой данных"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
    async def execute_query(self, query: str, params: tuple = ()):
        """Выполнение запроса с возвратом результата"""
        async with self.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                return await cursor.fetchall()
    
    async def execute_single(self, query: str, params: tuple = ()):
        """Выполнение запроса с возвратом одной записи"""
        async with self.get_connection() as conn:
            async with conn.execute(query, params) as cursor:
                return await cursor.fetchone()
    
    async def execute_write(self, query: str, params: tuple = ()):
        """Выполнение записи в БД"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.lastrowid
    
    async def execute_many(self, query: str, params_list: list):
        """Выполнение множественных запросов"""
        async with self.get_connection() as conn:
            await conn.executemany(query, params_list)
            await conn.commit()
    
    async def drop_db(self) -> None:
        """
        Удаление всех таблиц из базы данных.
        
        Удаляет все таблицы в следующем порядке:
        - take_profit_orders
        - limit_orders  
        - users
        """
        async with self.get_connection() as conn:
            # Получаем список всех таблиц
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = await cursor.fetchall()
            
            if not tables:
                logger.info("База данных пуста, нечего удалять")
                return
            
            # Удаляем таблицы в правильном порядке (с учетом внешних ключей)
            table_names = [table[0] for table in tables]
            logger.info(f"Найдены таблицы для удаления: {table_names}")
            
            # Отключаем проверку внешних ключей для безопасного удаления
            await conn.execute("PRAGMA foreign_keys = OFF")
            
            for table_name in table_names:
                try:
                    await conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                    logger.info(f"Таблица '{table_name}' удалена")
                except Exception as e:
                    logger.error(f"Ошибка при удалении таблицы '{table_name}': {e}")
            
            # Включаем обратно проверку внешних ключей
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.commit()
            
            logger.info("Все таблицы успешно удалены из базы данных")

db = DatabaseConnection()
