# agents/technical_agent.py

import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY
from state import PortfolioState


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=GROQ_API_KEY,
    temperature=0.2
)


TECHNICAL_PROMPT = """You are a technical analysis agent. Interpret these indicators.

Price data: {market_data}
Indicators: {technical_indicators}

Reference:
- RSI: <30 oversold (bullish signal), >70 overbought (bearish signal), 30-70 neutral
- MACD histogram: positive and rising = bullish momentum building, negative and falling = bearish
- Bollinger %: near 0 = price at lower band (potential bounce/bullish), near 1 = at upper band (potential pullback/bearish)
- Volume ratio: >1.5 means unusually high volume, which strengthens whatever signal is present; <0.7 means low conviction

Weigh all four together — don't just average them, look for confirmation or conflict between them.

Respond ONLY in strict JSON, no markdown fences:
{{
  "view": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "summary": "one or two sentences on what the technicals show"
}}
"""


def technical_node(state: PortfolioState) -> PortfolioState:
    market_data = state["market_data"]
    technical_indicators = state["technical_indicators"]

    prompt = TECHNICAL_PROMPT.format(
        market_data=json.dumps(market_data),
        technical_indicators=json.dumps(technical_indicators),
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
        f"[TechnicalAgent] view={result.get('view')} "
        f"confidence={result.get('confidence')}"
    ]

    return {
        "technical_analysis": result,
        "log": log
    }