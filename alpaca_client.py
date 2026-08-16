# alpaca_client.py
import requests
from config import FMP_API_KEY
from datetime import datetime, timedelta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

from alpaca.data.requests import StockLatestQuoteRequest

def get_latest_price(symbol: str) -> float:
    """Get the most recent tradeable price — use this for order pricing, not bars."""
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    quote = data_client.get_stock_latest_quote(request)[symbol]

    bid = quote.bid_price
    ask = quote.ask_price

    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    elif bid > 0:
        return bid  # no ask available, fall back to bid
    elif ask > 0:
        return ask  # no bid available, fall back to ask
    else:
        raise ValueError(f"No valid bid/ask for {symbol} — quote unusable")

def get_recent_bars(symbol: str, limit: int = 30):
    """Fetch recent daily bars for a symbol, explicit date range + IEX feed."""
    end = datetime.now() - timedelta(minutes=16)
    start = end - timedelta(days=90)  # wider window to guarantee enough trading days

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
        # no `limit` here — we want the full range, then slice ourselves
    )
    bars = data_client.get_stock_bars(request)
    bar_list = bars[symbol]

    # Ensure chronological order, then take the most recent `limit` bars
    bar_list = sorted(bar_list, key=lambda b: b.timestamp)[-limit:]

    print(f"[DEBUG] {symbol}: fetched {len(bar_list)} bars, most recent = {bar_list[-1].timestamp}")

    return bar_list

def get_open_orders(symbol: str = None):
    """Return currently open (unfilled) orders, optionally filtered by symbol."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol] if symbol else None)
    return trading_client.get_orders(filter=request)
def cancel_order(order_id: str):
    """Cancel a single open order by ID."""
    trading_client.cancel_order_by_id(order_id)


def cancel_all_orders():
    """Cancel every open order across all symbols."""
    trading_client.cancel_orders()
def get_account():
    return trading_client.get_account()


def get_positions():
    return trading_client.get_all_positions()



def get_fundamentals(symbol: str) -> dict:
    url = f"https://financialmodelingprep.com/stable/ratios-ttm?symbol={symbol}&apikey={FMP_API_KEY}"
    response = requests.get(url, timeout=10)

    try:
        data = response.json()
    except Exception:
        print(f"[WARN] FMP returned non-JSON response: {response.text[:200]}")
        return {}

    if not isinstance(data, list) or len(data) == 0:
        print(f"[WARN] FMP returned unexpected data for {symbol}: {data}")
        return {}

    ratios = data[0]
    return {
        "pe_ratio": ratios.get("priceToEarningsRatioTTM"),
        "peg_ratio": ratios.get("priceToEarningsGrowthRatioTTM"),
        "debt_to_equity": ratios.get("debtToEquityRatioTTM"),
        "roe": ratios.get("returnOnEquityTTM"),
        "current_ratio": ratios.get("currentRatioTTM"),
    }


def get_recent_news(symbol: str, limit: int = 5):
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest
    from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

    news_client = NewsClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    request = NewsRequest(symbols=symbol, limit=limit)
    news_set = news_client.get_news(request)

    # NewsSet behaves like a dict keyed by symbol, similar to bars
    articles = news_set.data.get(symbol, []) if hasattr(news_set, "data") else list(news_set)

    return [
        {"headline": a.headline, "summary": a.summary, "created_at": str(a.created_at)}
        for a in articles
    ]
def submit_bracket_order(symbol: str, qty: float, side: str, entry_price: float,
                          take_profit_price: float, stop_loss_price: float):
    order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

    order_request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
        stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2)),
    )

    order = trading_client.submit_order(order_request)
    return order

def submit_market_order(symbol: str, qty: float, side: str):
    """Simple market order, no bracket — used for closing/reducing existing positions."""
    order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
    order_request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )
    return trading_client.submit_order(order_request)