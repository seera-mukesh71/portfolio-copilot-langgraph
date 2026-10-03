# memory.py
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType
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
        properties=[
            Property(name="symbol", data_type=DataType.TEXT),
            Property(name="view", data_type=DataType.TEXT),
            Property(name="confidence", data_type=DataType.NUMBER),
            Property(name="rationale", data_type=DataType.TEXT),
            Property(name="side", data_type=DataType.TEXT),
            Property(name="approval_status", data_type=DataType.TEXT),
            Property(name="execution_status", data_type=DataType.TEXT),
            Property(name="timestamp", data_type=DataType.TEXT),
            Property(name="order_id", data_type=DataType.TEXT),
            Property(name="entry_price", data_type=DataType.NUMBER),
            Property(name="exit_price", data_type=DataType.NUMBER),
            Property(name="realized_pnl", data_type=DataType.NUMBER),
            Property(name="pnl_pct", data_type=DataType.NUMBER),
            Property(name="outcome", data_type=DataType.TEXT),
            Property(name="risk_method", data_type=DataType.TEXT),
        ],
    )


def store_decision(state: dict):
    """
    Persists a completed graph run (analysis + decision + outcome) to Weaviate
    so future runs can look back at similar past situations and learn from outcomes.
    """
    client = get_client()
    ensure_schema()

    collection = client.collections.get("TradeDecision")

    analysis = state.get("analysis", {})
    proposed_trade = state.get("proposed_trade", {})
    execution_result = state.get("execution_result", {})
    risk_check = state.get("risk_check", {})

    approval = state.get("approval_status", "none")
    exec_status = execution_result.get("status", "") if execution_result else ""

    if approval == "rejected":
        outcome = "rejected_by_human"
    elif exec_status == "submitted":
        outcome = "open_order_submitted"
    elif exec_status == "aborted":
        outcome = f"aborted_{execution_result.get('reason', 'drift')}"
    elif not risk_check.get("passed", False):
        outcome = "risk_gate_rejected"
    else:
        outcome = "neutral_no_trade"

    collection.data.insert({
        "symbol": state.get("symbol", ""),
        "view": analysis.get("view", "neutral"),
        "confidence": float(analysis.get("confidence", 0.0)),
        "rationale": analysis.get("rationale", ""),
        "side": proposed_trade.get("side", ""),
        "approval_status": approval,
        "execution_status": exec_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": str(execution_result.get("order_id", "")),
        "entry_price": float(execution_result.get("entry_price", proposed_trade.get("entry_price", 0.0))),
        "exit_price": 0.0,
        "realized_pnl": 0.0,
        "pnl_pct": 0.0,
        "outcome": outcome,
        "risk_method": risk_check.get("risk_method", ""),
    })


def reconcile_past_trades():
    """
    Checks Alpaca for closed orders / filled positions to calculate realized P&L
    and update past open trade decisions in Weaviate with their actual financial outcome.
    """
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca_client import trading_client

        client = get_client()
        ensure_schema()
        collection = client.collections.get("TradeDecision")

        # Fetch recent decisions that are open
        records = collection.query.fetch_objects(limit=20)
        
        # Get recently closed orders from Alpaca
        closed_orders = trading_client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50)
        )
        closed_by_symbol = {}
        for o in closed_orders:
            closed_by_symbol.setdefault(o.symbol, []).append(o)

        for obj in records.objects:
            props = obj.properties
            sym = props.get("symbol")
            current_outcome = props.get("outcome", "")

            # If trade was submitted and still pending outcome, check if closed
            if current_outcome in ["open_order_submitted", "pending_fill"] and sym in closed_by_symbol:
                matching_orders = closed_by_symbol[sym]
                for o in matching_orders:
                    if o.filled_avg_price and float(o.filled_avg_price) > 0:
                        entry_price = float(props.get("entry_price", 0.0))
                        fill_price = float(o.filled_avg_price)
                        side = props.get("side", "buy")
                        
                        if entry_price > 0:
                            if side == "buy":
                                pnl_pct = ((fill_price - entry_price) / entry_price) * 100
                            else:
                                pnl_pct = ((entry_price - fill_price) / entry_price) * 100
                            
                            outcome_tag = f"closed ({pnl_pct:+.1f}%)"
                            if pnl_pct > 0:
                                outcome_tag = f"profit ({pnl_pct:+.1f}%)"
                            elif pnl_pct < 0:
                                outcome_tag = f"loss ({pnl_pct:+.1f}%)"

                            collection.data.update(
                                uuid=obj.uuid,
                                properties={
                                    "exit_price": fill_price,
                                    "pnl_pct": round(pnl_pct, 2),
                                    "outcome": outcome_tag,
                                }
                            )
                            break
    except Exception as e:
        print(f"[WARN] Trade reconciliation failed: {e}")


def get_recent_decisions(symbol: str, limit: int = 5):
    """
    Fetches the most recent past decisions and trade outcomes for a symbol.
    """
    client = get_client()
    ensure_schema()

    collection = client.collections.get("TradeDecision")

    response = collection.query.fetch_objects(
        limit=limit,
        filters=weaviate.classes.query.Filter.by_property("symbol").equal(symbol),
    )

    results = []
    for obj in response.objects:
        p = obj.properties
        results.append({
            "timestamp": p.get("timestamp"),
            "view": p.get("view"),
            "confidence": p.get("confidence"),
            "side": p.get("side"),
            "outcome": p.get("outcome", "unknown"),
            "pnl_pct": p.get("pnl_pct", 0.0),
            "rationale": p.get("rationale", ""),
            "approval_status": p.get("approval_status"),
            "execution_status": p.get("execution_status"),
        })

    return results


def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None