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
BASE_URL = "https://api.bybit.com"  # URL for Bybit Futures API

@app.post("/")
async def webhook_listener(request: Request):
    data = await request.json()
    
    side = data.get("side", "buy")  # 'buy' or 'sell'
    symbol = data.get("symbol", "SOLUSDT")  # Default is SOLUSDT (Futures)
    leverage = data.get("leverage", 20)  # Leverage, default 20x
    entry_price = data.get("entry_price", 100)  # Default entry price
    
    # Get wallet balance for calculation
    async with httpx.AsyncClient() as client:
        wallet = await client.get(f"{BASE_URL}/v2/private/wallet/balance", params={"api_key": API_KEY, "symbol": symbol})
        balance = wallet.json().get('result', {}).get('totalWalletBalance', 0)
        
    margin = 0.90 * balance  # 90% of wallet balance used for trading
    quantity = margin / entry_price  # Quantity calculation
    
    # Calculate Take Profit, Stop Loss, and Trailing Stop levels
    tp_percent = 0.015  # +1.5% Take Profit
    sl_percent = 0.012  # -1.2% Stop Loss
    trailing_distance_percent = 0.014  # 1.4% Trailing Stop

    tp_price = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    sl_price = entry_price * (1 - sl_percent) if side == "buy" else entry_price * (1 + sl_percent)
    trailing_distance = int(trailing_distance_percent * 10000)  # Bybit wants trailing in ticks
    
    # Construct the order body for the Futures market
    order_body = {
        "category": "linear",  # Linear Perpetual Contract for Futures
        "side": side,  # buy or sell
        "symbol": symbol,  # Symbol (e.g., SOLUSDT for Futures)
        "leverage": leverage,  # Leverage
        "quantity": quantity,  # Quantity for the order
        "order_type": "Market",  # Market order
        "time_in_force": "GoodTillCancel",  # Order validity
        "price": entry_price  # Entry price from TradingView alert
    }
    
    # Send the order to the Bybit Futures API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/v2/private/order/create",  # Futures order endpoint
            headers={"X-BYBIT-APIKEY": API_KEY},
            json=order_body  # Send order body as JSON
        )
    
    # Send Take Profit and Stop Loss orders
    tp_sl_body = {
        "category": "linear",
        "symbol": symbol,
        "side": "sell" if side == "buy" else "buy",  # Reverse side for TP/SL orders
        "order_type": "Limit",
        "qty": quantity,
        "price": tp_price,
        "triggerPrice": tp_price,
        "triggerBy": "LastPrice",
        "timeInForce": "GoodTillCancel",
        "reduceOnly": True,
        "closeOnTrigger": True
    }

    sl_body = {
        "category": "linear",
        "symbol": symbol,
        "side": "sell" if side == "buy" else "buy",  # Reverse side for TP/SL orders
        "order_type": "Limit",
        "qty": quantity,
        "price": sl_price,
        "triggerPrice": sl_price,
        "triggerBy": "LastPrice",
        "timeInForce": "GoodTillCancel",
        "reduceOnly": True,
        "closeOnTrigger": True
    }

    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/v2/private/order/create", headers={"X-BYBIT-APIKEY": API_KEY}, json=tp_sl_body)
        await client.post(f"{BASE_URL}/v2/private/order/create", headers={"X-BYBIT-APIKEY": API_KEY}, json=sl_body)
    
    # Trailing Stop
    trailing_body = {
        "category": "linear",
        "symbol": symbol,
        "trailingStop": str(trailing_distance),  # Trailing stop distance in ticks
        "takeProfit": str(round(tp_price, 2)),
        "stopLoss": str(round(sl_price, 2)),
        "tpTriggerBy": "LastPrice",
        "slTriggerBy": "LastPrice"
    }

    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/v2/private/position/trading-stop", headers={"X-BYBIT-APIKEY": API_KEY}, json=trailing_body)

    return {"status": "Order placed with TP, SL, and trailing stop", "response": response.json()}
