# memory.py
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure, Property, DataType
from datetime import datetime, timezone

from config import WEAVIATE_URL, WEAVIATE_API_KEY

_client = None


def get_client():
    """Lazily create and reuse a single Weaviate client connection."""
    global _client
    if _client is None:
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,
            auth_credentials=Auth.api_key(WEAVIATE_API_KEY),
        )
    return _client


def ensure_schema():
    """Creates the TradeDecision collection if it doesn't already exist."""
    client = get_client()

    if client.collections.exists("TradeDecision"):
        return

    client.collections.create(
        name="TradeDecision",
        vectorizer_config=Configure.Vectorizer.text2vec_weaviate(),
        properties=[
            Property(name="symbol", data_type=DataType.TEXT),
            Property(name="view", data_type=DataType.TEXT),
            Property(name="confidence", data_type=DataType.NUMBER),
            Property(name="rationale", data_type=DataType.TEXT),
            Property(name="side", data_type=DataType.TEXT),
            Property(name="approval_status", data_type=DataType.TEXT),
            Property(name="execution_status", data_type=DataType.TEXT),
            Property(name="timestamp", data_type=DataType.TEXT),
        ],
    )


def store_decision(state: dict):
    """
    Persists a completed graph run (analysis + decision + outcome) to Weaviate
    so future runs can look back at similar past situations.
    """
    client = get_client()
    ensure_schema()

    collection = client.collections.get("TradeDecision")

    analysis = state.get("analysis", {})
    proposed_trade = state.get("proposed_trade", {})
    execution_result = state.get("execution_result", {})

    collection.data.insert({
        "symbol": state.get("symbol", ""),
        "view": analysis.get("view", ""),
        "confidence": analysis.get("confidence", 0.0),
        "rationale": analysis.get("rationale", ""),
        "side": proposed_trade.get("side", ""),
        "approval_status": state.get("approval_status", ""),
        "execution_status": execution_result.get("status", "") if execution_result else "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def get_recent_decisions(symbol: str, limit: int = 5):
    """
    Fetches the most recent past decisions for a symbol — this is what
    the analysis agent can reference as 'memory' of prior reasoning.
    """
    client = get_client()
    ensure_schema()

    collection = client.collections.get("TradeDecision")

    response = collection.query.fetch_objects(
        limit=limit,
        filters=weaviate.classes.query.Filter.by_property("symbol").equal(symbol),
    )

    return [obj.properties for obj in response.objects]


def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None