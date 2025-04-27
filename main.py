from fastapi import FastAPI, Request
import hmac
import hashlib
import time
import os
import httpx

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
    leverage = data.get("leverage", 20)
    entry_price = float(data.get("entry_price", 100))

    # Fixed margin to use (example 3 USDT)
    margin_to_use = 3
    quantity = (margin_to_use * leverage) / entry_price

    tp_percent = 0.015  # 1.5% Take Profit
    sl_percent = 0.012  # 1.2% Stop Loss
    trailing_percent = 0.014  # 1.4% Trailing Stop

    tp_price = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    sl_price = entry_price * (1 - sl_percent) if side == "buy" else entry_price * (1 + sl_percent)
    trailing_distance = int(trailing_percent * 10000)

    order_body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": round(quantity, 3),
        "timeInForce": "GoodTillCancel",
        "reduceOnly": False,
        "closeOnTrigger": False,
        "positionIdx": 0,
        "leverage": leverage
    }

    async with httpx.AsyncClient() as client:
        # Place market order
        order_response = await client.post(
            f"{BASE_URL}/v5/order/create",
            headers={"X-BYBIT-API-KEY": API_KEY},
            json=order_body
        )

        # Attach TP/SL and Trailing Stop
        if order_response.status_code == 200:
            tp_sl_body = {
                "category": "linear",
                "symbol": symbol,
                "takeProfit": str(round(tp_price, 2)),
                "stopLoss": str(round(sl_price, 2)),
                "trailingStop": str(trailing_distance),
                "tpTriggerBy": "LastPrice",
                "slTriggerBy": "LastPrice",
                "positionIdx": 0
            }
            await client.post(
                f"{BASE_URL}/v5/position/trading-stop",
                headers={"X-BYBIT-API-KEY": API_KEY},
                json=tp_sl_body
            )

    return {"status": "Order placed", "quantity": round(quantity, 3), "entry_price": entry_price}
