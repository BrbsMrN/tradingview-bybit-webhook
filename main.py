from fastapi import FastAPI, Request
import os
import httpx
import hmac
import hashlib
import time

app = FastAPI()

# API credentials
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api.bybit.com"

@app.post("/")
async def webhook_listener(request: Request):
    data = await request.json()

    side = data.get("side", "buy")
    symbol = data.get("symbol", "SOLUSDT")
    entry_price = float(data.get("entry_price", 100))
    leverage = 20  # Fixed leverage

    # Get Wallet Balance (Unified account type)
    timestamp = str(int(time.time() * 1000))
    params = {
        "api_key": API_KEY,
        "timestamp": timestamp
    }
    sign = hmac.new(API_SECRET.encode(), '&'.join([f"{k}={v}" for k, v in params.items()]).encode(), hashlib.sha256).hexdigest()
    params["sign"] = sign

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/v2/private/wallet/balance", params=params)
        wallet_data = response.json()

    balance = 0
    try:
        balance = float(wallet_data['result']['USDT']['wallet_balance'])
    except:
        balance = 0

    margin = balance * 0.90  # Χρησιμοποιούμε 90% του balance
    quantity = round((margin * leverage) / entry_price, 3)  # Quantity με leverage

    # Calculate TP, SL, Trailing
    tp_percent = 0.015
    sl_percent = 0.012
    trailing_distance_percent = 0.014

    tp_price = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    sl_price = entry_price * (1 - sl_percent) if side == "buy" else entry_price * (1 + sl_percent)
    trailing_distance = int(trailing_distance_percent * 10000)

    # Create position
    order_body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": quantity,
        "leverage": leverage,
        "timeInForce": "GoodTillCancel",
        "reduceOnly": False,
        "closeOnTrigger": False,
        "takeProfit": str(round(tp_price, 2)),
        "stopLoss": str(round(sl_price, 2)),
        "tpTriggerBy": "LastPrice",
        "slTriggerBy": "LastPrice",
        "trailingStop": str(trailing_distance)
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BASE_URL}/v5/order/create",
            headers={"X-BAPI-API-KEY": API_KEY},
            json=order_body
        )

    return {"status": "Order placed successfully!"}
