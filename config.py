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
STOP_LOSS_PCT = 0.03                       # 3% stop loss
TAKE_PROFIT_PCT = 0.06                     # 6% take profit