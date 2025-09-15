# -*- coding: utf-8 -*-
"""
Подписка фолловера на трейдера Bybit Copy Trading (USDT-M) с режимом Smart copy.
В начале выводит доступные USDT-балансы на фьючерсах (USDT-M) у трейдера и фолловера.

Требуется:
  - settings.TRADER_ID — UID элит-трейдера (СТОРОННЕГО!)
  - FOLLOWER_API_KEY / FOLLOWER_API_SECRET — ключи фолловера
  - (для показа баланса трейдера) settings.TRADER_API_* — ключи того трейдера

Управление:
  - COPY_AMOUNT_USDT — фонд копирования в USDT (>= 50)
  - COPY_ALL_POSITIONS — копировать уже открытые позиции трейдера (True/False)
"""

import os
import time
import hmac
import hashlib
import base64
import json
from urllib.parse import urlencode
import asyncio
import requests

# ========= Конфиг =========
from config.settings import settings

BYBIT_API_BASE = "https://api.bybit.com"

# Ключи фолловера — ИМИ подписываемся
FOLLOWER_API_KEY = os.getenv("FOLLOWER_API_KEY", "")
FOLLOWER_API_SECRET = os.getenv("FOLLOWER_API_SECRET", "")

# Ключи трейдера (нужны только чтобы показать его баланс в начале)
TRADER_API_KEY = getattr(settings, "TRADER_API_KEY", "") or ""
TRADER_API_SECRET = getattr(settings, "TRADER_API_SECRET", "") or ""

# Идентификатор элит-трейдера, на которого подписываемся
TRADER_ID = getattr(settings, "TRADER_ID", "")

# Параметры подписки
COPY_AMOUNT_USDT = int(os.getenv("COPY_AMOUNT_USDT", "500"))  # фонд копирования (>= 50)
COPY_ALL_POSITIONS = False  # True, чтобы подцепить текущие открытые позиции трейдера

# ========= Подпись/HTTP =========

_session = requests.Session()
_session.headers.update({"Content-Type": "application/json", "locale": "en-US"})

# кэш смещения времени (сервер - локально) в мс
_TIME_OFFSET_MS = 0


def _get_server_time_ms() -> int:
    """Получить серверное время Bybit (мс) и обновить смещение."""
    global _TIME_OFFSET_MS
    url = BYBIT_API_BASE + "/v5/market/time"
    r = _session.get(url, timeout=10)
    r.raise_for_status()
    j = r.json()
    server_ms = int(j["result"]["timeSecond"]) * 1000
    local_ms = int(time.time() * 1000)
    _TIME_OFFSET_MS = server_ms - local_ms
    return server_ms


def _ts_str() -> str:
    """Текущий timestamp (мс) с учётом смещения к серверному времени."""
    return str(int(time.time() * 1000 + _TIME_OFFSET_MS))


def _sign(api_key: str, secret: str, timestamp: str, method: str, request_path: str, body: str = "") -> str:
    """
    Bybit signature: HMAC SHA256(secret, timestamp + api_key + recv_window + body)
    """
    recv_window = "5000"  # 5 секунд окно
    prehash = f"{timestamp}{api_key}{recv_window}{body}"
    digest = hmac.new(secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def _headers(api_key: str, sign: str, timestamp: str) -> dict:
    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": sign,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": "5000",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, params: dict | None = None, data: dict | None = None):
    """
    Универсальный запрос к Bybit с корректной подписью.
    Использует FOLLOWER_* ключи (подписка/лимиты/списки и т.п.).
    """
    # Канонизированная query-строка
    query = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")

    # тело без пробелов
    body_str = ""
    if data is not None:
        body_str = json.dumps(data, separators=(",", ":"))

    # timestamp (при первом запросе пробуем синхронизироваться)
    ts = _ts_str()
    global _TIME_OFFSET_MS
    if _TIME_OFFSET_MS == 0:
        try:
            _get_server_time_ms()
            ts = _ts_str()
        except Exception:
            pass

    sign = _sign(
        FOLLOWER_API_KEY, FOLLOWER_API_SECRET, ts, method,
        path,
        body_str if method.upper() != "GET" else ""
    )
    headers = _headers(FOLLOWER_API_KEY, sign, ts)

    url = BYBIT_API_BASE + path + (f"?{query}" if query else "")
    resp = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Bybit API error {resp.status_code}: {resp.text}")
    j = resp.json()
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit API business error: {j}")
    return j.get("result")


def _request_with_keys(api_key: str, api_secret: str,
                       method: str, path: str, params: dict | None = None, data: dict | None = None):
    """
    То же самое, но с передачей произвольных ключей (для получения баланса трейдера/фолловера).
    """
    query = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")

    body_str = ""
    if data is not None:
        body_str = json.dumps(data, separators=(",", ":"))

    ts = _ts_str()
    global _TIME_OFFSET_MS
    if _TIME_OFFSET_MS == 0:
        try:
            _get_server_time_ms()
            ts = _ts_str()
        except Exception:
            pass

    sign = _sign(
        api_key, api_secret, ts, method,
        path,
        body_str if method.upper() != "GET" else ""
    )
    headers = _headers(api_key, sign, ts)

    url = BYBIT_API_BASE + path + (f"?{query}" if query else "")
    resp = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    resp.raise_for_status()
    j = resp.json()
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit API business error: {j}")
    return j.get("result")


# ========= Балансы =========

def get_futures_available_usdt(api_key: str, api_secret: str) -> float:
    """
    Возвращает доступный баланс (available) по USDT на USDT-M фьючерсах.
    GET /v5/account/wallet-balance?accountType=UNIFIED
      -> ищем запись с coin="USDT", берём поле "availableBalance".
    """
    data = _request_with_keys(
        api_key, api_secret,
        "GET", "/v5/account/wallet-balance",
        params={"accountType": "UNIFIED"},
        data=None
    )
    if not data or "list" not in data:
        return 0.0
    accounts = data["list"]
    if not accounts:
        return 0.0
    # Берем первый аккаунт (обычно основной)
    account = accounts[0]
    coins = account.get("coin", [])
    usdt_coin = next((c for c in coins if c.get("coin") == "USDT"), None)
    if not usdt_coin:
        return 0.0
    return float(usdt_coin.get("availableBalance", "0"))


# ========= Конкретные вызовы Copy Trading (Follower API) =========

def get_follow_limits(category: str = "linear", symbol: str | None = None):
    """
    GET /v5/copytrade/order/list
    (необязательно; полезно для валидации перед подпиской)
    """
    params = {"category": category}
    if symbol:
        params["symbol"] = symbol
    return _request("GET", "/v5/copytrade/order/list", params=params, data=None)


def follow_with_smart_copy(
    trader_id: str,
    copy_amount_usdt: int,
    *,
    copy_all_positions: bool = False,
    margin_mode: str = "cross",     # "cross" | "isolated"
    leverage_mode: str = "follow_trader",   # "follow_trader" | "fixed_leverage"
    multiple: int | None = None,            # нужно, если leverage_mode == "fixed_leverage"
    equity_guardian: bool = False,
    equity_guardian_mode: str = "amount",   # "amount" | "percentage"
    equity_value: int | None = None,
):
    """
    POST /v5/copytrade/order/create
    Обязательные: traderId, copyAmount (>= 50).
    Включает Smart copy: биржа открывает у фолловера ту же долю от copyAmount,
    какую трейдер открыл от своего элит-баланса.
    """
    payload = {
        "traderId": str(trader_id),
        "copyAmount": str(int(copy_amount_usdt)),
        "marginMode": margin_mode,
        "leverage": leverage_mode,
    }
    if copy_all_positions:
        payload["copyAllPositions"] = "yes"
    if leverage_mode == "fixed_leverage" and multiple:
        payload["multiple"] = str(int(multiple))
    if equity_guardian:
        payload["equityGuardian"] = "on"
        payload["equityGuardianMode"] = equity_guardian_mode
        if equity_value is None:
            raise ValueError("equity_value обязателен при включённом equity_guardian")
        payload["equity"] = str(int(equity_value))

    return _request("POST", "/v5/copytrade/order/create", params=None, data=payload)


def get_my_traders(page_no: int = 1, page_size: int = 20):
    """
    GET /v5/copytrade/order/list
    Список трейдеров, на кого уже подписан фолловер
    """
    params = {"page": page_no, "limit": page_size}
    return _request("GET", "/v5/copytrade/order/list", params=params, data=None)


def unfollow_trader(trader_id: str):
    """
    POST /v5/copytrade/order/cancel
    Отписка от трейдера
    """
    payload = {"traderId": str(trader_id)}
    return _request("POST", "/v5/copytrade/order/cancel", params=None, data=payload)


# ========= Основной сценарий =========

def main():
    # Проверки окружения
    if not FOLLOWER_API_KEY or not FOLLOWER_API_SECRET:
        raise SystemExit("FOLLOWER_API_KEY и FOLLOWER_API_SECRET не заданы в окружении")
    if not TRADER_ID:
        raise SystemExit("settings.TRADER_ID не задан (UID элит-трейдера)")

    # Балансы USDT на фьючерсах у трейдера и фолловера
    try:
        trader_fut = None
        if TRADER_API_KEY and TRADER_API_SECRET:
            trader_fut = get_futures_available_usdt(TRADER_API_KEY, TRADER_API_SECRET)
        else:
            print("WARN: не заданы settings.TRADER_API_* — пропускаю вывод баланса трейдера.")

        follower_fut = get_futures_available_usdt(FOLLOWER_API_KEY, FOLLOWER_API_SECRET)

        print(f"Trader USDT-M futures available: {trader_fut}")
        print(f"Follower USDT-M futures available: {follower_fut}")
    except Exception as e:
        print("WARN: не удалось получить фьючерсные балансы:", e)

    # (опционально) Проверим лимиты по продукту
    try:
        limits = get_follow_limits(category="linear")
        print("Follow limits (linear):", limits)
    except Exception as e:
        print("WARN: не удалось получить лимиты:", e)

    # Подписка Smart copy
    result = follow_with_smart_copy(
        trader_id=TRADER_ID,
        copy_amount_usdt=COPY_AMOUNT_USDT,
        copy_all_positions=COPY_ALL_POSITIONS,
        margin_mode="cross",
        leverage_mode="follow_trader",
    )
    print("Copy settings result:", result)

    # (опционально) Вывести список активных подписок
    try:
        traders = get_my_traders()
        print("My followed traders:", traders)
    except Exception as e:
        print("WARN: не удалось получить список подписок:", e)


if __name__ == "__main__":
    main()
