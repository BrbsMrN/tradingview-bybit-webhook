from fastapi import FastAPI, Request
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
    entry_price = float(data.get("entry_price", 100))
    leverage = 20  # Fixed leverage
    quantity = 0.5  # Fixed quantity per trade

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
        "side": side,
        "symbol": symbol,
        "leverage": leverage,
        "orderType": "Market",
        "qty": quantity,
        "timeInForce": "GoodTillCancel"
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BASE_URL}/v5/order/create",
            headers={"X-BYBIT-API-KEY": API_KEY},
            json=order_body
        )

    # Set TP, SL and Trailing Stop
    trailing_body = {
        "category": "linear",
        "symbol": symbol,
        "takeProfit": str(round(tp_price, 2)),
        "stopLoss": str(round(sl_price, 2)),
        "trailingStop": str(trailing_distance),
        "tpTriggerBy": "LastPrice",
        "slTriggerBy": "LastPrice"
    }

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BASE_URL}/v5/position/trading-stop",
            headers={"X-BYBIT-API-KEY": API_KEY},
            json=trailing_body
        )

    return {"status": "Order placed successfully!"}
