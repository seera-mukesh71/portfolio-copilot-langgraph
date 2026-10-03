# config.py
import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FMP_API_KEY = os.getenv("FMP_API_KEY")
# Trading parameters — tune these to taste
WATCHLIST = ["AAPL", "MSFT", "TSLA"]      # symbols the copilot monitors
MAX_POSITION_PCT = 0.10                    # max 10% of portfolio in one symbol
STOP_LOSS_PCT = 0.03                       # fallback 3% stop loss if ATR unavailable
TAKE_PROFIT_PCT = 0.06                     # fallback 6% take profit if ATR unavailable

# Volatility-adaptive risk & Execution parameters
ATR_WINDOW = 14
ATR_STOP_MULTIPLIER = 1.5                  # 1.5x ATR for dynamic stop loss
ATR_PROFIT_MULTIPLIER = 3.0                # 3.0x ATR for dynamic take profit (2:1 reward-to-risk)
MAX_PRICE_DRIFT_PCT = 0.02                 # 2% max allowed drift during approval delay before revalidation