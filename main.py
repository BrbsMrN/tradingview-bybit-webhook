from fastapi import FastAPI, Request
import hmac
import hashlib
import time
import os
import httpx

app = FastAPI()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api.bybit.com"

@app.post("/")
async def webhook_listener(request: Request):
    try:
        data = await request.json()

        if not data:
            return {"error": "Empty data received."}

        side = data.get("side", "").capitalize()  # Buy or Sell
        symbol = data.get("symbol", "SOLUSDT")
        leverage = data.get("leverage", 20)
        entry_price = float(data.get("entry_price", 100))

        async with httpx.AsyncClient() as client:
            wallet = await client.get(
                f"{BASE_URL}/v5/account/wallet-balance?accountType=UNIFIED",
                headers={
                    "X-BAPI-API-KEY": API_KEY,
                    "X-BAPI-SIGN": "",
                    "X-BAPI-TIMESTAMP": str(int(time.time() * 1000)),
                    "Content-Type": "application/json",
                }
            )
            wallet_json = wallet.json()
            balance = float(wallet_json["result"]["list"][0]["coin"][0]["walletBalance"])

            margin_to_use = balance * 0.9
            quantity = (margin_to_use * leverage) / entry_price

            # Order body
            order_body = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Market",
                "qty": round(quantity, 3),
                "timeInForce": "GoodTillCancel",
                "reduceOnly": False,
                "closeOnTrigger": False
            }

            # Submit market order
            order_response = await client.post(
                f"{BASE_URL}/v5/order/create",
                json=order_body,
                headers={
                    "X-BAPI-API-KEY": API_KEY,
                    "X-BAPI-SIGN": "",
                    "X-BAPI-TIMESTAMP": str(int(time.time() * 1000)),
                    "Content-Type": "application/json",
                }
            )

            return order_response.json()

    except Exception as e:
        return {"error": str(e)}
