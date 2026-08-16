# agents/execution_agent.py
from alpaca_client import submit_bracket_order, submit_market_order
from state import PortfolioState


def execution_node(state: PortfolioState) -> PortfolioState:
    trade = state["proposed_trade"]
    portfolio = state["portfolio"]
    log = state.get("log", [])

    if state.get("approval_status") != "approved":
        log.append("[ExecutionAgent] Skipped — trade not approved")
        return {**state, "execution_result": {"status": "skipped"}, "log": log}

    existing_qty = portfolio.get("existing_qty", 0.0)
    side = trade["side"]

    # If this trade closes/reduces an opposite existing position, it's an exit — no bracket allowed
    is_closing_trade = (
        (side == "buy" and existing_qty < 0) or
        (side == "sell" and existing_qty > 0)
    )

    try:
        if is_closing_trade:
            order = submit_market_order(
                symbol=trade["symbol"],
                qty=trade["qty"],
                side=trade["side"],
            )
            log.append(f"[ExecutionAgent] Closing trade — submitted as plain market order (no bracket)")
        else:
            order = submit_bracket_order(
                symbol=trade["symbol"],
                qty=trade["qty"],
                side=trade["side"],
                entry_price=trade["entry_price"],
                take_profit_price=trade["take_profit_price"],
                stop_loss_price=trade["stop_loss_price"],
            )

        result = {
            "status": "submitted",
            "order_id": str(order.id),
            "symbol": trade["symbol"],
            "qty": trade["qty"],
            "side": trade["side"],
            "type": "closing_market_order" if is_closing_trade else "bracket_entry",
        }
        log.append(f"[ExecutionAgent] Order submitted: {result}")
    except Exception as e:
        result = {"status": "error", "error": str(e)}
        log.append(f"[ExecutionAgent] Order failed: {e}")

    return {**state, "execution_result": result, "log": log}