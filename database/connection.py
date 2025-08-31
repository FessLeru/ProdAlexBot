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

db = DatabaseConnection()
