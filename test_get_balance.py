import asyncio
import ccxt.async_support as ccxt
from config.settings import settings

async def get_balance():
    """Получить баланс аккаунта через ccxt"""
    exchange = ccxt.bybit({
        'apiKey': settings.TRADER_API_KEY,
        'secret': settings.TRADER_API_SECRET,
        'sandbox': False,
        'enableRateLimit': True,
        'timeout': 10000,
    })

    print(settings.TRADER_API_KEY, settings.TRADER_API_SECRET)
    
    try:
        balance = await exchange.fetch_balance()
        print(f"💰 Баланс: {balance}")
        return balance
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(get_balance())
