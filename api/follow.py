# -*- coding: utf-8 -*-
"""
Подписка фолловера на трейдера Bitget Copy Trading (USDT-FUTURES) с режимом Smart copy.
В начале выводит доступные USDT-балансы на фьючерсах (USDT-M) у трейдера и фолловера.

Требуется:
  - settings.TRADER_ID — UID элит-трейдера (СТОРОННЕГО!)
  - FOLLOWER_API_KEY / FOLLOWER_API_SECRET / FOLLOWER_API_PASSPHRASE — ключи фолловера
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

BITGET_API_BASE = "https://api.bitget.com"

# Ключи фолловера — ИМИ подписываемся
FOLLOWER_API_KEY = os.getenv("FOLLOWER_API_KEY", "")
FOLLOWER_API_SECRET = os.getenv("FOLLOWER_API_SECRET", "")
FOLLOWER_API_PASSPHRASE = os.getenv("FOLLOWER_API_PASSPHRASE", "")

# Ключи трейдера (нужны только чтобы показать его баланс в начале)
TRADER_API_KEY = getattr(settings, "TRADER_API_KEY", "") or ""
TRADER_API_SECRET = getattr(settings, "TRADER_API_SECRET", "") or ""
TRADER_API_PASSPHRASE = getattr(settings, "TRADER_API_PASSPHRASE", "") or ""

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
    """Получить серверное время Bitget (мс) и обновить смещение."""
    global _TIME_OFFSET_MS
    url = BITGET_API_BASE + "/api/spot/v1/public/time"
    r = _session.get(url, timeout=10)
    r.raise_for_status()
    j = r.json()
    server_ms = int(j["data"])
    local_ms = int(time.time() * 1000)
    _TIME_OFFSET_MS = server_ms - local_ms
    return server_ms


def _ts_str() -> str:
    """Текущий timestamp (мс) с учётом смещения к серверному времени."""
    return str(int(time.time() * 1000 + _TIME_OFFSET_MS))


def _sign(secret: str, timestamp: str, method: str, request_path: str, body: str = "") -> str:
    """
    ACCESS-SIGN = base64(hmac_sha256(secret, timestamp + method + requestPath + body))
    ВАЖНО: requestPath ДОЛЖЕН включать ?query, если есть параметры.
    Для GET тело в подпись не добавляем.
    """
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _headers(api_key: str, passphrase: str, sign: str, timestamp: str) -> dict:
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
        "locale": "en-US",
    }


def _request(method: str, path: str, params: dict | None = None, data: dict | None = None):
    """
    Универсальный запрос к Bitget с корректной подписью.
    Использует FOLLOWER_* ключи (подписка/лимиты/списки и т.п.).
    """
    # Канонизированная query-строка
    query = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")

    # requestPath для подписи
    request_path_for_sign = path + (f"?{query}" if query else "")

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
        FOLLOWER_API_SECRET, ts, method,
        request_path_for_sign,
        body_str if method.upper() != "GET" else ""
    )
    headers = _headers(FOLLOWER_API_KEY, FOLLOWER_API_PASSPHRASE, sign, ts)

    url = BITGET_API_BASE + path + (f"?{query}" if query else "")
    resp = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Bitget API error {resp.status_code}: {resp.text}")
    j = resp.json()
    if j.get("code") != "00000":
        raise RuntimeError(f"Bitget API business error: {j}")
    return j.get("data")


def _request_with_keys(api_key: str, api_secret: str, passphrase: str,
                       method: str, path: str, params: dict | None = None, data: dict | None = None):
    """
    То же самое, но с передачей произвольных ключей (для получения баланса трейдера/фолловера).
    """
    query = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")
    request_path_for_sign = path + (f"?{query}" if query else "")

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
        api_secret, ts, method,
        request_path_for_sign,
        body_str if method.upper() != "GET" else ""
    )
    headers = _headers(api_key, passphrase, sign, ts)

    url = BITGET_API_BASE + path + (f"?{query}" if query else "")
    resp = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    resp.raise_for_status()
    j = resp.json()
    if j.get("code") != "00000":
        raise RuntimeError(f"Bitget API business error: {j}")
    return j.get("data")


# ========= Балансы =========

def get_futures_available_usdt(api_key: str, api_secret: str, passphrase: str) -> float:
    """
    Возвращает доступный баланс (available) по USDT на USDT-M фьючерсах.
    GET /api/v2/mix/account/accounts?productType=USDT-FUTURES
      -> ищем запись с marginCoin="USDT", берём поле "available".
    """
    data = _request_with_keys(
        api_key, api_secret, passphrase,
        "GET", "/api/v2/mix/account/accounts",
        params={"productType": "USDT-FUTURES"},
        data=None
    )
    if not data:
        return 0.0
    acc = next((a for a in data if a.get("marginCoin") == "USDT"), data[0])
    return float(acc.get("available", "0"))


# ========= Конкретные вызовы Copy Trading (Follower API) =========

def get_follow_limits(product_type: str = "USDT-FUTURES", symbol: str | None = None):
    """
    GET /api/v2/copy/mix-follower/query-quantity-limit
    (необязательно; полезно для валидации перед подпиской)
    """
    params = {"productType": product_type}
    if symbol:
        params["symbol"] = symbol
    return _request("GET", "/api/v2/copy/mix-follower/query-quantity-limit", params=params, data=None)


def follow_with_smart_copy(
    trader_id: str,
    copy_amount_usdt: int,
    *,
    copy_all_positions: bool = False,
    margin_mode: str = "follow_trader",     # "follow_trader" | "crossed_margin" | "isolated_margin"
    leverage_mode: str = "follow_trader",   # "follow_trader" | "fixed_leverage"
    multiple: int | None = None,            # нужно, если leverage_mode == "fixed_leverage"
    equity_guardian: bool = False,
    equity_guardian_mode: str = "amount",   # "amount" | "percentage"
    equity_value: int | None = None,
):
    """
    POST /api/v2/copy/mix-follower/copy-settings
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
        payload["copyAllPostions"] = "yes"  # (sic) орфография поля из доки
    if leverage_mode == "fixed_leverage" and multiple:
        payload["multiple"] = str(int(multiple))
    if equity_guardian:
        payload["equityGuardian"] = "on"
        payload["equityGuardianMode"] = equity_guardian_mode
        if equity_value is None:
            raise ValueError("equity_value обязателен при включённом equity_guardian")
        payload["equity"] = str(int(equity_value))

    return _request("POST", "/api/v2/copy/mix-follower/copy-settings", params=None, data=payload)


def get_my_traders(page_no: int = 1, page_size: int = 20):
    """
    GET /api/v2/copy/mix-follower/query-traders
    Список трейдеров, на кого уже подписан фолловер
    """
    params = {"pageNo": page_no, "pageSize": page_size}
    return _request("GET", "/api/v2/copy/mix-follower/query-traders", params=params, data=None)


def unfollow_trader(trader_id: str):
    """
    POST /api/v2/copy/mix-follower/cancel-trader
    Отписка от трейдера
    """
    payload = {"traderId": str(trader_id)}
    return _request("POST", "/api/v2/copy/mix-follower/cancel-trader", params=None, data=payload)


# ========= Основной сценарий =========

def main():
    # Проверки окружения
    if not FOLLOWER_API_KEY or not FOLLOWER_API_SECRET or not FOLLOWER_API_PASSPHRASE:
        raise SystemExit("FOLLOWER_API_* не заданы в окружении")
    if not TRADER_ID:
        raise SystemExit("settings.TRADER_ID не задан (UID элит-трейдера)")

    # Балансы USDT на фьючерсах у трейдера и фолловера
    try:
        trader_fut = None
        if TRADER_API_KEY and TRADER_API_SECRET and TRADER_API_PASSPHRASE:
            trader_fut = get_futures_available_usdt(TRADER_API_KEY, TRADER_API_SECRET, TRADER_API_PASSPHRASE)
        else:
            print("WARN: не заданы settings.TRADER_API_* — пропускаю вывод баланса трейдера.")

        follower_fut = get_futures_available_usdt(FOLLOWER_API_KEY, FOLLOWER_API_SECRET, FOLLOWER_API_PASSPHRASE)

        print(f"Trader USDT-M futures available: {trader_fut}")
        print(f"Follower USDT-M futures available: {follower_fut}")
    except Exception as e:
        print("WARN: не удалось получить фьючерсные балансы:", e)

    # (опционально) Проверим лимиты по продукту
    try:
        limits = get_follow_limits(product_type="USDT-FUTURES")
        print("Follow limits (USDT-FUTURES):", limits)
    except Exception as e:
        print("WARN: не удалось получить лимиты:", e)

    # Подписка Smart copy
    result = follow_with_smart_copy(
        trader_id=TRADER_ID,
        copy_amount_usdt=COPY_AMOUNT_USDT,
        copy_all_positions=COPY_ALL_POSITIONS,
        margin_mode="follow_trader",
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
