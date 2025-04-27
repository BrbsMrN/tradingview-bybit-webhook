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
        
    margin = 0.90 * balance  # Example of how to calculate margin based on wallet balance
    quantity = margin / entry_price  # Quantity calculation
    
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
    
    return {"status": "Order placed", "response": response.json()}
