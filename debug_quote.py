# debug_quote.py
from alpaca_client import get_recent_bars, data_client
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed

for symbol in ["AAPL", "MSFT", "TSLA"]:
    print(f"\n--- {symbol} ---")
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    quote = data_client.get_stock_latest_quote(request)[symbol]
    print(f"Raw quote: bid={quote.bid_price} ask={quote.ask_price} timestamp={quote.timestamp}")

    bars = get_recent_bars(symbol, limit=3)
    for bar in bars:
        print(f"Bar: {bar.timestamp} close={bar.close}")