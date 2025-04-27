from fastapi import FastAPI, Request
import hmac
import hashlib
import time
import httpx
import os

app = FastAPI()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

BASE_URL = "https://api.bybit.com"

@app.post("/")
async def webhook_listener(request: Request):
    data = await request.json()
    
    side = data.get("side", "Buy").capitalize()  # "Buy" ή "Sell"
    symbol = data.get("symbol", "SOLUSDT")
    leverage = data.get("leverage", 20)
    entry_price = data.get("entry_price", 150)
    
    # Λήψη wallet balance
    async with httpx.AsyncClient() as client:
        wallet = await client.get(
            f"{BASE_URL}/v5/account/wallet-balance?accountType=UNIFIED",
            headers={
                "X-BAPI-API-KEY": API_KEY,
                "X-BAPI-TIMESTAMP": str(int(time.time() * 1000)),
                "X-BAPI-RECV-WINDOW": "5000",
                "Content-Type": "application/json",
            }
        )
        balance = float(wallet.json()["result"]["list"][0]["coin"][0]["walletBalance"])
    
    margin_to_use = balance * 0.90
    quantity = (margin_to_use * leverage) / entry_price

    # Δημιουργία εντολής για άνοιγμα θέσης
    order_body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": str(round(quantity, 3)),
        "timeInForce": "GoodTillCancel",
        "reduceOnly": False,
        "closeOnTrigger": False
    }

    timestamp = str(int(time.time() * 1000))
    param_str = f"category=linear&closeOnTrigger=false&orderType=Market&qty={round(quantity, 3)}&reduceOnly=false&side={side}&symbol={symbol}&timeInForce=GoodTillCancel"
    signature = hmac.new(
        bytes(API_SECRET, "utf-8"),
        bytes(param_str + timestamp, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": "5000",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        entry = await client.post(f"{BASE_URL}/v5/order/create", headers=headers, json=order_body)

    # Ορισμός Take Profit, Stop Loss και Trailing Stop
    tp_percent = 0.015  # +1.5% TP
    sl_percent = 0.012  # -1.2% SL
    trailing_distance_percent = 0.014  # 1.4% Trailing Stop

    base_price = entry_price
    tp_price = base_price * (1 + tp_percent) if side == "Buy" else base_price * (1 - tp_percent)
    sl_price = base_price * (1 - sl_percent) if side == "Buy" else base_price * (1 + sl_percent)
    trailing_distance = int(trailing_distance_percent * 10000)  # Bybit θέλει ticks

    # Εντολή Trading-Stop
    trailing_body = {
        "category": "linear",
        "symbol": symbol,
        "trailingStop": str(trailing_distance),
        "takeProfit": str(round(tp_price, 2)),
        "stopLoss": str(round(sl_price, 2)),
        "tpTriggerBy": "LastPrice",
        "slTriggerBy": "LastPrice"
    }

    param_list = f"category=linear&symbol={symbol}&takeProfit={round(tp_price,2)}&tpTriggerBy=LastPrice&stopLoss={round(sl_price,2)}&slTriggerBy=LastPrice&trailingStop={trailing_distance}"
    timestamp2 = str(int(time.time() * 1000))
    signature2 = hmac.new(
        bytes(API_SECRET, "utf-8"),
        bytes(param_list + timestamp2, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers2 = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-SIGN": signature2,
        "X-BAPI-TIMESTAMP": timestamp2,
        "X-BAPI-RECV-WINDOW": "5000",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        trailing = await client.post(f"{BASE_URL}/v5/position/trading-stop", headers=headers2, json=trailing_body)

    return {"status": "entry + tp/sl + trailing created"}
