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


def get_similar_decisions(query_text: str, symbol: str = None, limit: int = 5):
    """
    Performs true semantic vector/hybrid search across all historical trade decisions
    to find past market setups, indicator patterns, and reasoning similar to the current situation.
    """
    client = get_client()
    ensure_schema()

    collection = client.collections.get("TradeDecision")

    try:
        # Build optional symbol filter if requested
        where_filter = None
        if symbol:
            where_filter = weaviate.classes.query.Filter.by_property("symbol").equal(symbol)

        response = collection.query.hybrid(
            query=query_text,
            filters=where_filter,
            limit=limit,
        )

        results = []
        for obj in response.objects:
            p = obj.properties
            results.append({
                "symbol": p.get("symbol"),
                "timestamp": p.get("timestamp"),
                "view": p.get("view"),
                "confidence": p.get("confidence"),
                "side": p.get("side"),
                "outcome": p.get("outcome", "unknown"),
                "pnl_pct": p.get("pnl_pct", 0.0),
                "rationale": p.get("rationale", ""),
                "risk_method": p.get("risk_method", ""),
                "approval_status": p.get("approval_status"),
                "execution_status": p.get("execution_status"),
            })
        return results
    except Exception as e:
        print(f"[WARN] Hybrid vector search failed, falling back to recent query: {e}")
        return get_recent_decisions(symbol=symbol if symbol else "AAPL", limit=limit)


def reconcile_past_trades():
    """
    Checks Alpaca by EXACT order ID and child bracket legs to calculate realized P&L
    and update past open trade decisions in Weaviate with their actual financial outcome.
    """
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca_client import trading_client

        client = get_client()
        ensure_schema()
        collection = client.collections.get("TradeDecision")

        # Fetch recent decisions that are open / awaiting fill outcome
        records = collection.query.fetch_objects(limit=30)
        
        # Get all closed orders from Alpaca (including parent and bracket legs)
        closed_orders = trading_client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=100)
        )
        closed_order_map = {str(o.id): o for o in closed_orders}

        for obj in records.objects:
            props = obj.properties
            order_id = str(props.get("order_id", "")).strip()
            current_outcome = str(props.get("outcome", ""))

            if not order_id or current_outcome not in ["open_order_submitted", "pending_fill"]:
                continue

            # 1. Check exact parent order status
            parent_order = closed_order_map.get(order_id)
            if not parent_order:
                try:
                    parent_order = trading_client.get_order_by_id(order_id)
                except Exception:
                    parent_order = None

            if not parent_order:
                continue

            # Check if parent order was canceled / expired before fill
            if parent_order.status.value in ["canceled", "expired", "rejected"]:
                collection.data.update(
                    uuid=obj.uuid,
                    properties={"outcome": f"order_{parent_order.status.value}"}
                )
                continue

            # If parent order filled, check if any closing leg filled
            entry_price = float(parent_order.filled_avg_price) if parent_order.filled_avg_price else float(props.get("entry_price", 0.0))
            side = props.get("side", "buy")
            sym = props.get("symbol")

            # Check matching exit fills for this symbol that filled after this parent order
            for c_id, c_order in closed_order_map.items():
                if c_id == order_id:
                    continue  # skip parent itself
                
                # Check if it is a child leg or matching closing fill for the same symbol
                if c_order.symbol == sym and c_order.filled_avg_price and float(c_order.filled_avg_price) > 0:
                    # Closing order has opposite side
                    is_exit_fill = (
                        (side == "buy" and c_order.side.value == "sell") or
                        (side == "sell" and c_order.side.value == "buy")
                    )
                    
                    if is_exit_fill and c_order.filled_at and parent_order.filled_at and c_order.filled_at >= parent_order.filled_at:
                        exit_price = float(c_order.filled_avg_price)
                        if entry_price > 0:
                            if side == "buy":
                                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                            else:
                                pnl_pct = ((entry_price - exit_price) / entry_price) * 100

                            order_type_tag = c_order.order_type.value if hasattr(c_order, "order_type") else "exit"
                            if pnl_pct > 0:
                                outcome_tag = f"take_profit (+{pnl_pct:.1f}%)"
                            elif pnl_pct < 0:
                                outcome_tag = f"stopped_out ({pnl_pct:.1f}%)"
                            else:
                                outcome_tag = f"closed_breakeven (0.0%)"

                            collection.data.update(
                                uuid=obj.uuid,
                                properties={
                                    "exit_price": exit_price,
                                    "pnl_pct": round(pnl_pct, 2),
                                    "outcome": outcome_tag,
                                }
                            )
                            break
    except Exception as e:
        print(f"[WARN] Exact order ID trade reconciliation failed: {e}")


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