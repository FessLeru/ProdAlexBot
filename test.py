import asyncio
import ccxt.async_support as ccxt
from decimal import Decimal, ROUND_DOWN
from config.settings import settings


async def get_size_from_notional(exchange: ccxt.bitget, symbol: str, notional_usdt: float) -> float:
    """
    Возвращает количество контрактов (size) для указанного НОМИНАЛА сделки (USDT).
    Плечо тут НЕ учитываем — оно влияет только на требуемую маржу, а не на номинал.
    """
    ticker = await exchange.fetch_ticker(symbol)
    last = ticker.get("last") or ticker.get("close")
    if not last:
        raise RuntimeError(f"Не удалось получить цену для {symbol}")

    market = exchange.market(symbol)
    contract_size = market.get("contractSize", 1)

    raw_size = Decimal(str(notional_usdt)) / (Decimal(str(last)) * Decimal(str(contract_size)))
    raw_size = raw_size.quantize(Decimal("1.00000000"), rounding=ROUND_DOWN)
    return float(exchange.amount_to_precision(symbol, float(raw_size)))


async def main():
    exchange = ccxt.bitget({
        "apiKey": settings.TRADER_API_KEY,
        "secret": settings.TRADER_API_SECRET,
        "password": settings.TRADER_API_PASSPHRASE,
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",       # только USDT-свапы
            "fetchCurrencies": False,
        }
    })
    exchange.has["fetchCurrencies"] = False

    symbol = "GRT/USDT:USDT"
    notional_usdt = 1.2
    leverage = 20

    try:
        # загрузка рынков
        await exchange.load_markets(reload=True, params={"type": "swap"})
        market = exchange.market(symbol)
        print("Инфо о рынке:", {k: market[k] for k in ("symbol", "type", "contractSize", "limits") if k in market})

        # Установка плеча
        try:
            await exchange.set_leverage(leverage, symbol, params={"marginCoin": "USDT"})
            print(f"Плечо установлено: {leverage}x")
        except Exception as e:
            print("Не удалось установить плечо:", e)

        # расчет размера
        size = await get_size_from_notional(exchange, symbol, notional_usdt)

        # проверка минимума
        ticker = await exchange.fetch_ticker(symbol)
        last = Decimal(str(ticker.get("last") or ticker.get("close")))
        contract_size = Decimal(str(market.get("contractSize", 1)))
        notional_est = Decimal(str(size)) * last * contract_size

        required_margin = notional_est / Decimal(leverage)
        print(f"Оценка маржи при {leverage}x: ~{required_margin:.6f} USDT (номинал ≈ {notional_est:.4f} USDT)")

        params = {
            "marginMode": "cross",
            "marginCoin": "USDT",
            "timeInForceValue": "normal",
        }

        print(f"Создаём MARKET BUY на {notional_usdt} USDT → {size} контракт(ов) {symbol}...")
        order = await exchange.create_market_order(
            symbol=symbol,
            side="buy",
            amount=size,
            params=params
        )
        print("Ордер создан:", order)

    except Exception as e:
        print("Ошибка:", e)
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())
