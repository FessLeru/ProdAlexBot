import asyncio
from celery import Celery
from celery.signals import worker_ready
import logging
from decimal import Decimal

from config.settings import settings
from config.constants import COINS, RESTART_DELAY
from trading.order_tracker import OrderTracker

logger = logging.getLogger(__name__)

# Инициализация Celery с оптимизированными настройками
celery_app = Celery(
    'bybit_trading_bot',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Конфигурация для максимальной производительности
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    
    # Оптимизация для множества задач
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Настройки для быстрой обработки
    task_compression='gzip',
    result_compression='gzip',
    
    # Роутинг задач
    task_routes={
        'trading.celery_worker.start_symbol_trading': {'queue': 'trading'},
        'trading.celery_worker.track_symbol_continuously': {'queue': 'tracking'},
        'trading.celery_worker.restart_symbol_after_delay': {'queue': 'restart'},
    },
    
    # Таймауты
    task_soft_time_limit=300,  # 5 минут
    task_time_limit=600,       # 10 минут
)

@worker_ready.connect
def at_start(sender, **kwargs):
    """Инициализация при запуске воркера"""
    logger.info("🚀 Celery воркер запущен и готов к работе")

@celery_app.task(bind=True, name='start_master_trading')
def start_master_trading(self, api_key: str, api_secret: str, deposit_per_coin: float = 100.0):
    """
    Мастер-задача для запуска торговли по всем монетам
    
    Args:
        api_key: API ключ
        api_secret: API секрет
        deposit_per_coin: Депозит на каждую монету в USDT
    """
    logger.info("🎯 Запуск мастер-задачи торговли")
    
    try:
        # Запускаем задачи для каждой монеты
        for coin in COINS:
            start_symbol_trading.delay(
                symbol=coin,
                api_key=api_key,
                api_secret=api_secret,
                deposit_amount=deposit_per_coin
            )
            logger.info(f"📊 Запущена торговля для {coin}")
        
        logger.info(f"✅ Запущено {len(COINS)} торговых задач")
        return f"Started trading for {len(COINS)} coins"
        
    except Exception as e:
        logger.error(f"❌ Ошибка в мастер-задаче: {e}")
        raise

@celery_app.task(bind=True, name='start_symbol_trading')
def start_symbol_trading(self, symbol: str, api_key: str, api_secret: str, deposit_amount: float):
    """
    Запуск торговли для конкретной монеты
    
    Args:
        symbol: Торговый символ
        api_key: API ключ  
        api_secret: API секрет
        deposit_amount: Размер депозита
    """
    logger.info(f"🚀 Запуск торговли для {symbol}")
    
    async def run_trading():
        try:
            tracker = OrderTracker(api_key, api_secret)
            
            # Запускаем торговлю
            success = await tracker.start_trading_for_symbol(
                symbol=symbol,
                deposit_amount=Decimal(str(deposit_amount))
            )
            
            if success:
                # Если успешно запустили - переходим к отслеживанию
                track_symbol_continuously.delay(
                    symbol=symbol,
                    api_key=api_key,
                    api_secret=api_secret,
                    deposit_amount=deposit_amount
                )
                logger.info(f"✅ Торговля запущена для {symbol}, переходим к отслеживанию")
            else:
                logger.error(f"❌ Не удалось запустить торговлю для {symbol}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка запуска торговли {symbol}: {e}")
            raise
    
    # Запускаем в новом event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_trading())
    finally:
        loop.close()

@celery_app.task(bind=True, name='track_symbol_continuously')
def track_symbol_continuously(self, symbol: str, api_key: str, api_secret: str, deposit_amount: float):
    """
    Непрерывное отслеживание ордеров для символа
    
    Args:
        symbol: Торговый символ
        api_key: API ключ
        api_secret: API секрет  
        deposit_amount: Размер депозита
    """
    logger.info(f"👁️ Начинаем отслеживание {symbol}")
    
    async def run_tracking():
        try:
            tracker = OrderTracker(api_key, api_secret)
            
            # Отслеживаем ордера
            result = await tracker.track_symbol_orders(symbol)
            
            if result == 'restart':
                # Тейк-профит исполнен - планируем перезапуск
                logger.info(f"🔄 Планируем перезапуск {symbol} через {RESTART_DELAY} сек")
                
                restart_symbol_after_delay.apply_async(
                    args=[symbol, api_key, api_secret, deposit_amount],
                    countdown=RESTART_DELAY
                )
            else:
                # Продолжаем отслеживание
                track_symbol_continuously.apply_async(
                    args=[symbol, api_key, api_secret, deposit_amount],
                    countdown=2  # Проверяем каждые 2 секунды
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка отслеживания {symbol}: {e}")
            # Перезапускаем отслеживание через 5 секунд при ошибке
            track_symbol_continuously.apply_async(
                args=[symbol, api_key, api_secret, deposit_amount],
                countdown=5
            )
    
    # Запускаем в новом event loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_tracking())
    finally:
        loop.close()

@celery_app.task(bind=True, name='restart_symbol_after_delay')
def restart_symbol_after_delay(self, symbol: str, api_key: str, api_secret: str, deposit_amount: float):
    """
    Перезапуск торговли для символа после задержки
    
    Args:
        symbol: Торговый символ
        api_key: API ключ
        api_secret: API секрет
        deposit_amount: Размер депозита
    """
    logger.info(f"🔄 Перезапуск торговли для {symbol}")
    
    # Просто запускаем новую торговлю
    start_symbol_trading.delay(
        symbol=symbol,
        api_key=api_key,
        api_secret=api_secret,
        deposit_amount=deposit_amount
    )

# Вспомогательные задачи для мониторинга

@celery_app.task(name='get_trading_status')
def get_trading_status():
    """
    Получение статуса торговли по всем монетам
    
    Returns:
        dict: Статус торговли
    """
    # Здесь можно добавить логику получения статуса из Redis
    # Пока возвращаем базовую информацию
    
    return {
        'active_coins': len(COINS),
        'coins': COINS,
        'status': 'running',
        'timestamp': asyncio.get_event_loop().time()
    }

@celery_app.task(name='stop_all_trading')
def stop_all_trading():
    """
    Остановка всей торговли (отмена всех задач)
    
    Returns:
        str: Результат остановки
    """
    try:
        # Получаем все активные задачи
        active_tasks = celery_app.control.inspect().active()
        
        if active_tasks:
            # Отменяем все задачи торговли
            for worker_name, tasks in active_tasks.items():
                for task in tasks:
                    if task['name'].startswith('trading.celery_worker'):
                        celery_app.control.revoke(task['id'], terminate=True)
                        logger.info(f"🛑 Отменена задача {task['id']}")
        
        logger.info("🛑 Все торговые задачи остановлены")
        return "All trading tasks stopped"
        
    except Exception as e:
        logger.error(f"❌ Ошибка остановки торговли: {e}")
        return f"Error stopping trading: {e}"


@celery_app.task(name='health_check')
def health_check():
    """
    Проверка здоровья воркера
    
    Returns:
        dict: Статус воркера
    """
    return {
        'status': 'healthy',
        'timestamp': asyncio.get_event_loop().time(),
        'worker_id': health_check.request.id,
        'active_coins': len(COINS)
    }

if __name__ == '__main__':
    # Запуск воркера для разработки
    celery_app.start()