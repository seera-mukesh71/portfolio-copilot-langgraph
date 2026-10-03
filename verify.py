import os
import sys

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

print("=" * 65)
print("🔍 PORTFOLIO COPILOT - SYSTEM HEALTH & VERIFICATION CHECK")
print("=" * 65)

# 1. API Keys Check
print("\n[1/5] Checking Environment Keys...")
keys = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "GROQ_API_KEY", "FMP_API_KEY", "WEAVIATE_URL", "WEAVIATE_API_KEY"]
all_keys_ok = True
for k in keys:
    val = os.getenv(k)
    if val:
        masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
        print(f"  ✅ {k}: OK ({masked})")
    else:
        print(f"  ❌ {k}: MISSING")
        all_keys_ok = False

# 2. Alpaca Account & Market Data
print("\n[2/5] Testing Alpaca Paper Trading & Market Data...")
try:
    from alpaca_client import get_account, get_positions, get_latest_price, get_recent_bars, get_recent_news
    account = get_account()
    print(f"  ✅ Account Connected: Status={account.status}, Equity=${float(account.equity):,.2f}, Cash=${float(account.cash):,.2f}")
    
    price = get_latest_price("AAPL")
    bars = get_recent_bars("AAPL", limit=5)
    news = get_recent_news("AAPL", limit=2)
    print(f"  ✅ Market Data AAPL: Latest Price=${price:.2f}, Fetched {len(bars)} daily bars, {len(news)} news items.")
except Exception as e:
    print(f"  ❌ Alpaca Test Failed: {e}")

# 3. Fundamental Data (FMP)
print("\n[3/5] Testing Financial Modeling Prep (FMP) API...")
try:
    from alpaca_client import get_fundamentals
    funds = get_fundamentals("AAPL")
    print(f"  ✅ FMP Fundamentals AAPL: P/E={funds.get('pe_ratio')}, PEG={funds.get('peg_ratio')}, Debt/Eq={funds.get('debt_to_equity')}")
except Exception as e:
    print(f"  ❌ FMP Test Failed: {e}")

# 4. Groq LLM
print("\n[4/5] Testing Groq LLM...")
try:
    from langchain_groq import ChatGroq
    from config import GROQ_API_KEY, GROQ_MODEL
    llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.1)
    res = llm.invoke("Reply with exactly: LLM_READY")
    print(f"  ✅ Groq LLM ({GROQ_MODEL}): {res.content.strip()}")
except Exception as e:
    print(f"  ❌ Groq LLM Test Failed: {e}")

# 5. Weaviate Memory & P&L Reconcile
print("\n[5/5] Testing Weaviate Memory & Trade Reconciliation...")
try:
    from memory import get_client, ensure_schema, get_recent_decisions, reconcile_past_trades, close_client
    client = get_client()
    ready = client.is_ready()
    ensure_schema()
    reconcile_past_trades()
    past = get_recent_decisions("AAPL", limit=2)
    print(f"  ✅ Weaviate Cloud: Ready={ready}, Schema OK, Found {len(past)} past AAPL decisions in memory.")
    close_client()
except Exception as e:
    print(f"  ❌ Weaviate Test Failed: {e}")

print("\n" + "=" * 65)
print("🎉 SYSTEM CHECK COMPLETE")
print("=" * 65)
