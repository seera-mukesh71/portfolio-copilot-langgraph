# agents/portfolio_agent.py
from alpaca_client import get_account, get_positions, get_open_orders
from state import PortfolioState


def portfolio_node(state: PortfolioState) -> PortfolioState:
    account = get_account()
    positions = get_positions()
    symbol = state["symbol"]

    existing_position = next((p for p in positions if p.symbol == symbol), None)

    open_orders = get_open_orders(symbol=symbol)
    pending_qty = sum(
        float(o.qty) if o.side.value == "buy" else -float(o.qty)
        for o in open_orders
    )

    portfolio = {
        "cash": float(account.cash),
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
        "existing_qty": float(existing_position.qty) if existing_position else 0.0,
        "existing_avg_entry": float(existing_position.avg_entry_price) if existing_position else None,
        "pending_qty": pending_qty,
        "total_positions": len(positions),
    }

    log = [f"[PortfolioAgent] equity={portfolio['equity']}, cash={portfolio['cash']}, existing_qty({symbol})={portfolio['existing_qty']}, pending_qty={pending_qty}"]
    return {"portfolio": portfolio, "log": log}