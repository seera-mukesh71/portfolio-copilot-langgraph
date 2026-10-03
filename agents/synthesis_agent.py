# agents/synthesis_agent.py
import json
from unittest import result
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, GROQ_MODEL
from state import PortfolioState
from memory import get_recent_decisions

llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.2)

SYNTHESIS_PROMPT = """You are the senior decision-maker synthesizing three specialist reports 
for {symbol} into one final trading view.

Technical analysis: {technical}
Fundamental analysis: {fundamental}
News sentiment: {news}

Past decisions for this symbol (your own memory, most recent first): {past_decisions}

Guidance:
- If all three specialists agree, confidence should be high.
- If they conflict (e.g. technicals bullish but fundamentals bearish), lean toward the 
  majority view but lower your confidence to reflect the disagreement.
- Weight technical analysis most heavily for short-term trades, but let strong fundamental 
  or news signals override weak/neutral technicals.
- If two or more specialists returned neutral due to missing data, be conservative — 
  lower confidence rather than assuming things are fine.
- Reference past decisions if there's a repeating pattern (e.g. you were right or wrong before).

Respond ONLY in strict JSON, no markdown fences:
{{
  "view": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "rationale": "two to three sentences explaining the synthesis and any conflicts weighed"
}}
"""


def synthesis_node(state: PortfolioState) -> PortfolioState:
    symbol = state["symbol"]
    technical = state.get("technical_analysis", {})
    fundamental = state.get("fundamental_analysis", {})
    news = state.get("news_analysis", {})

    try:
        past_decisions = get_recent_decisions(symbol, limit=5)
    except Exception as e:
        past_decisions = []
        print(f"[WARN] Could not fetch memory for {symbol}: {e}")

    prompt = SYNTHESIS_PROMPT.format(
        symbol=symbol,
        technical=json.dumps(technical),
        fundamental=json.dumps(fundamental),
        news=json.dumps(news),
        past_decisions=json.dumps(past_decisions) if past_decisions else "No past decisions yet.",
    )

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
    except Exception as e:
        result = {"view": "neutral", "confidence": 0.0, "rationale": f"error: {e}"}

    log = [f"[SynthesisAgent] final view={result.get('view')} confidence={result.get('confidence')} (tech={technical.get('view')}, fund={fundamental.get('view')}, news={news.get('view')})"]
    return {"analysis": result, "log": log}