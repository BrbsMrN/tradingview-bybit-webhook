from fastapi import FastAPI, Request
import hmac
import hashlib
import time
import httpx
import os

app = FastAPI()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

BASE_URL = "https://api.bybit.com"  # Live environment

@app.post("/")
async def webhook_listener(request: Request):
    data = await request.json()
    
    side = data.get("side", "Buy")  # ή "Sell"
    symbol = data.get("symbol", "SOLUSDT")
    leverage = data.get("leverage", 20)
    entry_price = data.get("price", 150)
    
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

    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": str(round(quantity, 3)),
        "timeInForce": "GoodTillCancel",
        "reduceOnly": False,
        "closeOnTrigger": False
    }

    param_str = f"category=linear&closeOnTrigger=false&orderType=Market&qty={round(quantity, 3)}&reduceOnly=false&side={side}&symbol={symbol}&timeInForce=GoodTillCancel"
    timestamp = str(int(time.time() * 1000))
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
        res = await client.post(f"{BASE_URL}/v5/order/create", headers=headers, json=body)
        return res.json()
