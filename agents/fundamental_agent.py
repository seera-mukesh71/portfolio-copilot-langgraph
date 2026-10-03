# agents/fundamental_agent.py

import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, GROQ_MODEL
from state import PortfolioState
from alpaca_client import get_fundamentals


llm = ChatGroq(
    model=GROQ_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0.2
)


FUNDAMENTAL_PROMPT = """You are a fundamental analysis agent. Interpret these ratios for {symbol}.

Fundamentals: {fundamentals}

Reference:
- P/E ratio: high P/E (>30) suggests growth expectations or overvaluation; low P/E (<15) suggests value or concern
- PEG ratio: <1 suggests undervalued relative to growth, >2 suggests overvalued
- Debt/Equity: high values (>2) indicate leverage risk
- ROE: higher is generally better, shows efficient use of equity
- Current ratio: >1.5 is healthy short-term liquidity, <1 is a red flag

If fundamentals are missing or empty, say so honestly and return neutral with low confidence — do not guess.

Respond ONLY in strict JSON, no markdown fences:
{{
  "view": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "summary": "one or two sentences on financial health"
}}
"""


def fundamental_node(state: PortfolioState) -> PortfolioState:
    symbol = state["symbol"]

    try:
        fundamentals = get_fundamentals(symbol)
    except Exception as e:
        fundamentals = {}
        print(f"[WARN] Could not fetch fundamentals for {symbol}: {e}")

    prompt = FUNDAMENTAL_PROMPT.format(
        symbol=symbol,
        fundamentals=json.dumps(fundamentals)
    )

    try:
        response = llm.invoke(prompt)

        raw = (
            response.content
            .strip()
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        result = json.loads(raw)

    except Exception as e:
        result = {
            "view": "neutral",
            "confidence": 0.0,
            "summary": f"error: {e}"
        }

    # Return ONLY this node's new log entry.
    # Do not read or append to the existing state["log"].
    log = [
        f"[FundamentalAgent] view={result.get('view')} "
        f"confidence={result.get('confidence')}"
    ]

    return {
        "fundamental_analysis": result,
        "log": log
    }