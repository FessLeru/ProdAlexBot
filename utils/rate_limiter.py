import asyncio
import time
from collections import deque
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60, max_concurrent: int = 5):
        self.max_requests = max_requests
        self.window = window
        self.max_concurrent = max_concurrent
        
        # Очередь временных меток запросов
        self.request_times = deque()
        
        # Семафор для ограничения одновременных запросов
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Статистика по эндпоинтам
        self.endpoint_stats: Dict[str, deque] = {}
        
        # Блокировка для thread-safety
        self.lock = asyncio.Lock()
    
    async def acquire(self, endpoint: str = "default", priority: int = 0):
        """Получение разрешения на запрос с приоритетом"""
        async with self.semaphore:
            async with self.lock:
                current_time = time.time()
                
                # Очищаем старые запросы
                while self.request_times and current_time - self.request_times[0] > self.window:
                    self.request_times.popleft()
                
                # Очищаем статистику по эндпоинту
                if endpoint not in self.endpoint_stats:
                    self.endpoint_stats[endpoint] = deque()
                
                endpoint_queue = self.endpoint_stats[endpoint]
                while endpoint_queue and current_time - endpoint_queue[0] > self.window:
                    endpoint_queue.popleft()
                
                # Проверяем лимиты
                if len(self.request_times) >= self.max_requests:
                    sleep_time = self.window - (current_time - self.request_times[0]) + 0.1
                    logger.warning(f"Rate limit достигнут, ожидание {sleep_time:.2f} сек")
                    await asyncio.sleep(sleep_time)
                    return await self.acquire(endpoint, priority)
                
                # Адаптивная задержка для эндпоинта
                endpoint_delay = self._calculate_endpoint_delay(endpoint)
                if endpoint_delay > 0:
                    await asyncio.sleep(endpoint_delay)
                
                # Записываем время запроса
                self.request_times.append(current_time)
                endpoint_queue.append(current_time)
                
                return True
    
    def _calculate_endpoint_delay(self, endpoint: str) -> float:
        """Расчет адаптивной задержки для эндпоинта"""
        if endpoint not in self.endpoint_stats:
            return 0
        
        queue = self.endpoint_stats[endpoint]
        if len(queue) < 5:
            return 0
        
        # Если много запросов к одному эндпоинту - увеличиваем задержку
        recent_requests = len([t for t in queue if time.time() - t < 10])
        if recent_requests > 10:
            return 0.5
        elif recent_requests > 5:
            return 0.2
        
        return 0
    
    async def wait_if_needed(self):
        """Ожидание если достигнут лимит"""
        async with self.lock:
            current_time = time.time()
            
            # Очищаем старые запросы
            while self.request_times and current_time - self.request_times[0] > self.window:
                self.request_times.popleft()
            
            if len(self.request_times) >= self.max_requests:
                sleep_time = self.window - (current_time - self.request_times[0]) + 0.1
                await asyncio.sleep(sleep_time)
    
    def get_stats(self) -> Dict:
        """Получение статистики использования"""
        current_time = time.time()
        recent_requests = len([t for t in self.request_times if current_time - t < 60])
        
        endpoint_stats = {}
        for endpoint, queue in self.endpoint_stats.items():
            recent_endpoint_requests = len([t for t in queue if current_time - t < 60])
            endpoint_stats[endpoint] = recent_endpoint_requests
        
        return {
            "total_recent_requests": recent_requests,
            "max_requests": self.max_requests,
            "window": self.window,
            "endpoint_stats": endpoint_stats,
            "available_slots": self.semaphore._value
        }
