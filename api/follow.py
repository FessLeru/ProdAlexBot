"""
Модуль для работы с Bybit Copy Trading API.
Обеспечивает автоматическое копирование сделок трейдера с процентным соотношением.
"""

import os
import time
import hmac
import hashlib
import base64
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
import asyncio
import requests

# ========= Конфиг =========
from config.settings import settings

BYBIT_API_BASE = "https://api.bybit.com"

# Ключи фолловера — ИМИ подписываемся
FOLLOWER_API_KEY: str = os.getenv("FOLLOWER_API_KEY", "")
FOLLOWER_API_SECRET: str = os.getenv("FOLLOWER_API_SECRET", "")

# Ключи трейдера (нужны только чтобы показать его баланс в начале)
TRADER_API_KEY: str = getattr(settings, "TRADER_API_KEY", "") or ""
TRADER_API_SECRET: str = getattr(settings, "TRADER_API_SECRET", "") or ""

# Идентификатор элит-трейдера, на которого подписываемся
TRADER_ID: str = getattr(settings, "TRADER_ID", "")

# Параметры подписки
COPY_AMOUNT_USDT: int = int(os.getenv("COPY_AMOUNT_USDT", "500"))  # фонд копирования (>= 50)
COPY_ALL_POSITIONS: bool = False  # True, чтобы подцепить текущие открытые позиции трейдера

# ========= Подпись/HTTP =========

_session: requests.Session = requests.Session()
_session.headers.update({"Content-Type": "application/json", "locale": "en-US"})

# кэш смещения времени (сервер - локально) в мс
_TIME_OFFSET_MS: int = 0


def _get_server_time_ms() -> int:
    """
    Получить серверное время Bybit (мс) и обновить смещение.
    
    Returns:
        int: Серверное время в миллисекундах.
        
    Raises:
        requests.RequestException: При ошибке HTTP запроса.
        KeyError: При неожиданном формате ответа API.
    """
    global _TIME_OFFSET_MS
    url: str = BYBIT_API_BASE + "/v5/market/time"
    r: requests.Response = _session.get(url, timeout=10)
    r.raise_for_status()
    j: Dict[str, Any] = r.json()
    server_ms: int = int(j["result"]["timeSecond"]) * 1000
    local_ms: int = int(time.time() * 1000)
    _TIME_OFFSET_MS = server_ms - local_ms
    return server_ms


def _ts_str() -> str:
    """
    Получить текущий timestamp (мс) с учётом смещения к серверному времени.
    
    Returns:
        str: Текущий timestamp в миллисекундах в виде строки.
    """
    return str(int(time.time() * 1000 + _TIME_OFFSET_MS))


def _sign(api_key: str, secret: str, timestamp: str, method: str, request_path: str, body: str = "") -> str:
    """
    Создать подпись для Bybit API запроса.
    
    Bybit signature: HMAC SHA256(secret, timestamp + api_key + recv_window + body)
    
    Args:
        api_key (str): API ключ.
        secret (str): Секретный ключ.
        timestamp (str): Временная метка.
        method (str): HTTP метод.
        request_path (str): Путь запроса.
        body (str, optional): Тело запроса. По умолчанию "".
        
    Returns:
        str: HMAC SHA256 подпись в hex формате.
    """
    recv_window: str = "5000"  # 5 секунд окно
    prehash: str = f"{timestamp}{api_key}{recv_window}{body}"
    digest: str = hmac.new(secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def _headers(api_key: str, sign: str, timestamp: str) -> Dict[str, str]:
    """
    Создать заголовки для Bybit API запроса.
    
    Args:
        api_key (str): API ключ.
        sign (str): Подпись запроса.
        timestamp (str): Временная метка.
        
    Returns:
        Dict[str, str]: Словарь с заголовками HTTP запроса.
    """
    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": sign,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": "5000",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Any:
    """
    Универсальный запрос к Bybit с корректной подписью.
    Использует FOLLOWER_* ключи (подписка/лимиты/списки и т.п.).
    
    Args:
        method (str): HTTP метод (GET, POST, etc.).
        path (str): Путь API endpoint.
        params (Optional[Dict[str, Any]]): Параметры запроса.
        data (Optional[Dict[str, Any]]): Данные для POST запроса.
        
    Returns:
        Any: Результат API запроса.
        
    Raises:
        RuntimeError: При ошибке API запроса или бизнес-логики.
    """
    # Канонизированная query-строка
    query: str = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")

    # тело без пробелов
    body_str: str = ""
    if data is not None:
        body_str = json.dumps(data, separators=(",", ":"))

    # timestamp (при первом запросе пробуем синхронизироваться)
    ts: str = _ts_str()
    global _TIME_OFFSET_MS
    if _TIME_OFFSET_MS == 0:
        try:
            _get_server_time_ms()
            ts = _ts_str()
        except Exception:
            pass

    sign: str = _sign(
        FOLLOWER_API_KEY, FOLLOWER_API_SECRET, ts, method,
        path,
        body_str if method.upper() != "GET" else ""
    )
    headers: Dict[str, str] = _headers(FOLLOWER_API_KEY, sign, ts)

    url: str = BYBIT_API_BASE + path + (f"?{query}" if query else "")
    resp: requests.Response = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    if not resp.ok:
        raise RuntimeError(f"Bybit API error {resp.status_code}: {resp.text}")
    j: Dict[str, Any] = resp.json()
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit API business error: {j}")
    return j.get("result")


def _request_with_keys(api_key: str, api_secret: str,
                       method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Any:
    """
    Универсальный запрос к Bybit с произвольными API ключами.
    Используется для получения баланса трейдера/фолловера.
    
    Args:
        api_key (str): API ключ.
        api_secret (str): Секретный ключ.
        method (str): HTTP метод (GET, POST, etc.).
        path (str): Путь API endpoint.
        params (Optional[Dict[str, Any]]): Параметры запроса.
        data (Optional[Dict[str, Any]]): Данные для POST запроса.
        
    Returns:
        Any: Результат API запроса.
        
    Raises:
        RuntimeError: При ошибке API запроса или бизнес-логики.
    """
    query: str = ""
    if params:
        query = urlencode(sorted(params.items()), doseq=True, safe=":/")

    body_str: str = ""
    if data is not None:
        body_str = json.dumps(data, separators=(",", ":"))

    ts: str = _ts_str()
    global _TIME_OFFSET_MS
    if _TIME_OFFSET_MS == 0:
        try:
            _get_server_time_ms()
            ts = _ts_str()
        except Exception:
            pass

    sign: str = _sign(
        api_key, api_secret, ts, method,
        path,
        body_str if method.upper() != "GET" else ""
    )
    headers: Dict[str, str] = _headers(api_key, sign, ts)

    url: str = BYBIT_API_BASE + path + (f"?{query}" if query else "")
    resp: requests.Response = _session.request(method.upper(), url, headers=headers, data=(body_str or None), timeout=15)
    resp.raise_for_status()
    j: Dict[str, Any] = resp.json()
    if j.get("retCode") != 0:
        raise RuntimeError(f"Bybit API business error: {j}")
    return j.get("result")


# ========= Балансы =========

def get_futures_available_usdt(api_key: str, api_secret: str) -> float:
    """
    Получить доступный баланс USDT на USDT-M фьючерсах.
    
    Args:
        api_key (str): API ключ.
        api_secret (str): Секретный ключ.
        
    Returns:
        float: Доступный баланс USDT.
        
    Raises:
        RuntimeError: При ошибке API запроса.
    """
    data: Any = _request_with_keys(
        api_key, api_secret,
        "GET", "/v5/account/wallet-balance",
        params={"accountType": "UNIFIED"},
        data=None
    )
    if not data or "list" not in data:
        return 0.0
    accounts: List[Dict[str, Any]] = data["list"]
    if not accounts:
        return 0.0
    # Берем первый аккаунт (обычно основной)
    account: Dict[str, Any] = accounts[0]
    coins: List[Dict[str, Any]] = account.get("coin", [])
    usdt_coin: Optional[Dict[str, Any]] = next((c for c in coins if c.get("coin") == "USDT"), None)
    if not usdt_coin:
        return 0.0
    return float(usdt_coin.get("availableBalance", "0"))


# ========= Конкретные вызовы Copy Trading (Follower API) =========

def get_follow_limits(category: str = "linear", symbol: Optional[str] = None) -> Any:
    """
    Получить лимиты копирования для указанной категории и символа.
    
    Args:
        category (str): Категория торговли. По умолчанию "linear".
        symbol (Optional[str]): Торговый символ. По умолчанию None.
        
    Returns:
        Any: Лимиты копирования.
        
    Raises:
        RuntimeError: При ошибке API запроса.
    """
    params: Dict[str, str] = {"category": category}
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
    multiple: Optional[int] = None,            # нужно, если leverage_mode == "fixed_leverage"
    equity_guardian: bool = False,
    equity_guardian_mode: str = "amount",   # "amount" | "percentage"
    equity_value: Optional[int] = None,
) -> Any:
    """
    Подписаться на трейдера с использованием Smart Copy.
    
    Smart Copy автоматически копирует сделки в процентном соотношении:
    если трейдер открыл позицию на 10% от своего баланса, 
    фолловер откроет позицию на 10% от своего copy_amount.
    
    Args:
        trader_id (str): ID трейдера для подписки.
        copy_amount_usdt (int): Сумма для копирования в USDT (минимум 50).
        copy_all_positions (bool): Копировать все текущие позиции трейдера.
        margin_mode (str): Режим маржи ("cross" или "isolated").
        leverage_mode (str): Режим плеча ("follow_trader" или "fixed_leverage").
        multiple (Optional[int]): Множитель плеча (только для fixed_leverage).
        equity_guardian (bool): Включить защиту капитала.
        equity_guardian_mode (str): Режим защиты ("amount" или "percentage").
        equity_value (Optional[int]): Значение для защиты капитала.
        
    Returns:
        Any: Результат подписки.
        
    Raises:
        ValueError: При некорректных параметрах.
        RuntimeError: При ошибке API запроса.
    """
    if copy_amount_usdt < 50:
        raise ValueError("copy_amount_usdt должен быть >= 50 USDT")
    
    if leverage_mode == "fixed_leverage" and multiple is None:
        raise ValueError("multiple обязателен при leverage_mode='fixed_leverage'")
    
    if equity_guardian and equity_value is None:
        raise ValueError("equity_value обязателен при включённом equity_guardian")
    
    payload: Dict[str, str] = {
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
        payload["equity"] = str(int(equity_value))

    return _request("POST", "/v5/copytrade/order/create", params=None, data=payload)


def get_my_traders(page_no: int = 1, page_size: int = 20) -> Any:
    """
    Получить список трейдеров, на которых подписан фолловер.
    
    Args:
        page_no (int): Номер страницы. По умолчанию 1.
        page_size (int): Размер страницы. По умолчанию 20.
        
    Returns:
        Any: Список трейдеров с информацией о подписках.
        
    Raises:
        RuntimeError: При ошибке API запроса.
    """
    params: Dict[str, int] = {"page": page_no, "limit": page_size}
    return _request("GET", "/v5/copytrade/order/list", params=params, data=None)


def unfollow_trader(trader_id: str) -> Any:
    """
    Отписаться от трейдера.
    
    Args:
        trader_id (str): ID трейдера для отписки.
        
    Returns:
        Any: Результат отписки.
        
    Raises:
        RuntimeError: При ошибке API запроса.
    """
    payload: Dict[str, str] = {"traderId": str(trader_id)}
    return _request("POST", "/v5/copytrade/order/cancel", params=None, data=payload)


# ========= Основной сценарий =========

def main() -> None:
    """
    Основная функция для подписки на трейдера с Smart Copy.
    
    Выполняет:
    1. Проверку конфигурации
    2. Получение балансов трейдера и фолловера
    3. Подписку на трейдера с процентным копированием
    4. Вывод списка активных подписок
    
    Raises:
        SystemExit: При отсутствии обязательных параметров конфигурации.
    """
    # Проверки окружения
    if not FOLLOWER_API_KEY or not FOLLOWER_API_SECRET:
        raise SystemExit("FOLLOWER_API_KEY и FOLLOWER_API_SECRET не заданы в окружении")
    if not TRADER_ID:
        raise SystemExit("settings.TRADER_ID не задан (UID элит-трейдера)")

    # Балансы USDT на фьючерсах у трейдера и фолловера
    try:
        trader_fut: Optional[float] = None
        if TRADER_API_KEY and TRADER_API_SECRET:
            trader_fut = get_futures_available_usdt(TRADER_API_KEY, TRADER_API_SECRET)
        else:
            print("WARN: не заданы settings.TRADER_API_* — пропускаю вывод баланса трейдера.")

        follower_fut: float = get_futures_available_usdt(FOLLOWER_API_KEY, FOLLOWER_API_SECRET)

        print(f"Trader USDT-M futures available: {trader_fut}")
        print(f"Follower USDT-M futures available: {follower_fut}")
    except Exception as e:
        print("WARN: не удалось получить фьючерсные балансы:", e)

    # (опционально) Проверим лимиты по продукту
    try:
        limits: Any = get_follow_limits(category="linear")
        print("Follow limits (linear):", limits)
    except Exception as e:
        print("WARN: не удалось получить лимиты:", e)

    # Подписка Smart copy с процентным копированием
    try:
        result: Any = follow_with_smart_copy(
            trader_id=TRADER_ID,
            copy_amount_usdt=COPY_AMOUNT_USDT,
            copy_all_positions=COPY_ALL_POSITIONS,
            margin_mode="cross",
            leverage_mode="follow_trader",  # Ключевой параметр для процентного копирования
        )
        print("Smart Copy subscription result:", result)
        print("✅ Подписка успешно создана! Теперь сделки будут копироваться в процентном соотношении.")
    except Exception as e:
        print(f"❌ Ошибка при создании подписки: {e}")
        return

    # (опционально) Вывести список активных подписок
    try:
        traders: Any = get_my_traders()
        print("My followed traders:", traders)
    except Exception as e:
        print("WARN: не удалось получить список подписок:", e)


if __name__ == "__main__":
    main()
