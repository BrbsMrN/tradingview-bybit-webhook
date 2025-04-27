from fastapi import FastAPI, Request
import os
import httpx

app = FastAPI()

# API credentials
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api.bybit.com"  # Bybit Futures API URL

@app.post("/")
async def webhook_listener(request: Request):
    data = await request.json()

    side = data.get("side", "buy")  # buy or sell
    symbol = data.get("symbol", "SOLUSDT")  # e.g., SOLUSDT
    leverage = data.get("leverage", 20)  # default leverage 20
    entry_price = float(data.get("entry_price", 100))  # default price

    fixed_usdt = 10  # Θέση 10$
    quantity = fixed_usdt / entry_price  # Υπολογισμός quantity

    # Υπολογισμοί για TP, SL και Trailing
    tp_percent = 0.015  # +1.5%
    sl_percent = 0.012  # -1.2%
    trailing_percent = 0.014  # 1.4%

    tp_price = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    sl_price = entry_price * (1 - sl_percent) if side == "buy" else entry_price * (1 + sl_percent)
    trailing_distance = int(trailing_percent * 10000)  # σε ticks

    # Φτιάχνουμε την εντολή αγοράς
    order_body = {
        "category": "linear",
        "symbol": symbol,
        "side": side,
        "orderType": "Market",
        "qty": round(quantity, 3),
        "leverage": leverage,
        "timeInForce": "GoodTillCancel",
        "reduceOnly": False
    }

    headers = {
        "X-BYBIT-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/v5/order/create", headers=headers, json=order_body)

        # Φτιάχνουμε trailing stop
        trailing_body = {
            "category": "linear",
            "symbol": symbol,
            "takeProfit": round(tp_price, 2),
            "stopLoss": round(sl_price, 2),
            "trailingStop": trailing_distance,
            "tpTriggerBy": "LastPrice",
            "slTriggerBy": "LastPrice"
        }
        await client.post(f"{BASE_URL}/v5/position/trading-stop", headers=headers, json=trailing_body)

    return {"status": "Order Sent!"}
