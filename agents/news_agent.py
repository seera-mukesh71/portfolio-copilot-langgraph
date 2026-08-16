# agents/news_agent.py

import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY
from state import PortfolioState
from alpaca_client import get_recent_news


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=GROQ_API_KEY,
    temperature=0.2
)


NEWS_PROMPT = """You are a news sentiment agent. Read these recent headlines for {symbol}
and assess overall sentiment.

Headlines: {headlines}

If there are no headlines, return neutral with low confidence — do not invent sentiment.

Respond ONLY in strict JSON, no markdown fences:
{{
  "view": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "summary": "one or two sentences on what the news suggests"
}}
"""


def news_node(state: PortfolioState) -> PortfolioState:
    symbol = state["symbol"]

    try:
        news_items = get_recent_news(symbol, limit=5)
    except Exception as e:
        news_items = []
        print(f"[WARN] Could not fetch news for {symbol}: {e}")

    headlines = [
        item["headline"] for item in news_items
    ] if news_items else []

    prompt = NEWS_PROMPT.format(
        symbol=symbol,
        headlines=json.dumps(headlines)
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
        f"[NewsAgent] view={result.get('view')} "
        f"confidence={result.get('confidence')}"
    ]

    return {
        "news_analysis": result,
        "log": log
    }