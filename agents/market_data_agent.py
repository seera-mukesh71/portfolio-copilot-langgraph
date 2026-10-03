# agents/market_data_agent.py
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands, AverageTrueRange

from alpaca_client import get_recent_bars
from state import PortfolioState


def market_data_node(state: PortfolioState) -> PortfolioState:
    symbol = state["symbol"]
    bars = get_recent_bars(symbol, limit=60)  # need more history for indicators

    if len(bars) < 30:
        raise ValueError(f"Only {len(bars)} bars returned for {symbol} — insufficient for indicators.")

    df = pd.DataFrame({
        "close": [b.close for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "volume": [b.volume for b in bars],
    })

    last_close = df["close"].iloc[-1]
    avg_close_30d = df["close"].tail(30).mean()
    avg_close_5d = df["close"].tail(5).mean()

    rsi = RSIIndicator(close=df["close"], window=14).rsi().iloc[-1]

    macd_calc = MACD(close=df["close"])
    macd_line = macd_calc.macd().iloc[-1]
    macd_signal = macd_calc.macd_signal().iloc[-1]
    macd_hist = macd_calc.macd_diff().iloc[-1]

    bb = BollingerBands(close=df["close"], window=20, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_pct = (last_close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

    # Volatility - Average True Range (ATR)
    atr_calc = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
    atr = atr_calc.average_true_range().iloc[-1]
    atr_pct = (atr / last_close * 100) if last_close > 0 else 0.0

    avg_volume_30d = df["volume"].tail(30).mean()
    latest_volume = df["volume"].iloc[-1]
    volume_ratio = latest_volume / avg_volume_30d if avg_volume_30d > 0 else 1.0

    market_data = {
        "symbol": symbol,
        "last_close": float(round(last_close, 2)),
        "avg_close_30d": float(round(avg_close_30d, 2)),
        "avg_close_5d": float(round(avg_close_5d, 2)),
        "pct_vs_30d_avg": float(round((last_close - avg_close_30d) / avg_close_30d * 100, 2)),
        "pct_vs_5d_avg": float(round((last_close - avg_close_5d) / avg_close_5d * 100, 2)),
    }

    technical_indicators = {
        "rsi_14": float(round(rsi, 2)),
        "macd_line": float(round(macd_line, 3)),
        "macd_signal": float(round(macd_signal, 3)),
        "macd_histogram": float(round(macd_hist, 3)),
        "bollinger_pct": float(round(bb_pct, 2)),
        "volume_ratio": float(round(volume_ratio, 2)),
        "atr": float(round(atr, 2)),
        "atr_pct": float(round(atr_pct, 2)),
    }

    log = [f"[MarketDataAgent] {symbol} close={last_close} rsi={technical_indicators['rsi_14']} macd_hist={technical_indicators['macd_histogram']} atr={technical_indicators['atr']} ({technical_indicators['atr_pct']}%)"]
    return {"market_data": market_data, "technical_indicators": technical_indicators, "log": log}