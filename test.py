import asyncio
import ccxt.async_support as ccxt
from decimal import Decimal, ROUND_DOWN
from config.settings import settings


async def get_size_from_notional(exchange: ccxt.bybit, symbol: str, notional_usdt: float) -> float:
    """
    Возвращает количество контрактов (size) для указанного НОМИНАЛА сделки (USDT).
    Плечо НЕ учитываем — оно влияет только на требуемую маржу, а не на номинал.
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
    exchange = ccxt.bybit({
        "apiKey": settings.TRADER_API_KEY,
        "secret": settings.TRADER_API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",       # только USDT-свапы
            "fetchCurrencies": False,
        }
    })
    exchange.has["fetchCurrencies"] = False

    symbol = "GRT/USDT:USDT"
    notional_usdt = 1
    leverage = 20

    # --- на сколько выше входа ставить TP (пример: +1.5%) ---
    tp_percent = 0.015  # 1.5%

    try:
        # Загрузка рынков
        await exchange.load_markets(reload=True, params={"type": "swap"})
        market = exchange.market(symbol)
        print("Инфо о рынке:", {k: market[k] for k in ("symbol", "type", "contractSize", "limits") if k in market})

        # Установка режима позиций (обязательно для Bybit)
        try:
            await exchange.set_position_mode(False, symbol)  # False = One-Way Mode
            print("Режим позиций установлен: One-Way")
        except Exception as e:
            print("Не удалось установить режим позиций:", e)

        # Установка режима маржи
        try:
            await exchange.set_margin_mode("cross", symbol)  # cross margin
            print("Режим маржи установлен: Cross")
        except Exception as e:
            print("Не удалось установить режим маржи:", e)

        # Установка плеча
        try:
            await exchange.set_leverage(leverage, symbol)
            print(f"Плечо установлено: {leverage}x")
        except Exception as e:
            print("Не удалось установить плечо:", e)

        # Расчёт размера по номиналу
        size = await get_size_from_notional(exchange, symbol, notional_usdt)

        # Оценка маржи
        ticker = await exchange.fetch_ticker(symbol)
        last = Decimal(str(ticker.get("last") or ticker.get("close")))
        contract_size = Decimal(str(market.get("contractSize", 1)))
        notional_est = Decimal(str(size)) * last * contract_size
        required_margin = notional_est / Decimal(leverage)
        print(f"Оценка маржи при {leverage}x: ~{required_margin:.6f} USDT (номинал ≈ {notional_est:.4f} USDT)")

        # Общие параметры ордеров
        common_params = {
            "timeInForce": "GTC",          # для LIMIT-TP
            "positionIdx": 0,              # One-Way Mode
        }

        # --- 1) MARKET BUY ---
        print(f"Создаём MARKET BUY на {notional_usdt} USDT → {size} контракт(ов) {symbol}...")
        entry_order = await exchange.create_market_order(
            symbol=symbol,
            side="buy",
            amount=size,
            params=common_params
        )
        print("Ордер (вход) создан:", entry_order)

        tp_amount = float(entry_order.get("filled") or entry_order.get("amount") or size)
        tp_amount = float(exchange.amount_to_precision(symbol, tp_amount))

        # Цена тейк-профита: от текущей последней цены (или цены сделки, если хочешь — возьми entry_order['average'])
        last_price = float(entry_order.get("average") or last)
        tp_price = last_price * (1.0 + float(tp_percent))
        tp_price = float(exchange.price_to_precision(symbol, tp_price))

        # --- 2) LIMIT SELL reduce-only как отдельный ТЕЙК-ПРОФИТ ---
        # reduceOnly гарантирует закрытие (уменьшение) позиции, а не открытие встречной.
        tp_params = {
            **common_params,
            "reduceOnly": True,
            "positionIdx": 0,              # One-Way Mode
        }

        print(f"Ставим TP: LIMIT SELL reduce-only {tp_amount} @ {tp_price} ({tp_percent*100:.2f}%)...")
        tp_order = await exchange.create_order(
            symbol=symbol,
            type="limit",
            side="sell",
            amount=tp_amount,
            price=tp_price,
            params=tp_params,
        )
        print("Тейк-профит создан:", tp_order)

    except Exception as e:
        print("Ошибка:", e)
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())
