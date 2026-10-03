# agents/execution_agent.py
from alpaca_client import submit_bracket_order, submit_market_order, get_latest_price
from config import MAX_PRICE_DRIFT_PCT, ATR_STOP_MULTIPLIER, ATR_PROFIT_MULTIPLIER
from state import PortfolioState


def execution_node(state: PortfolioState) -> PortfolioState:
    trade = state["proposed_trade"]
    portfolio = state["portfolio"]
    log = []
    symbol = trade["symbol"]

    if state.get("approval_status") != "approved":
        log.append("[ExecutionAgent] Skipped — trade not approved")
        return {"execution_result": {"status": "skipped"}, "log": log}

    # --- Stale Trade Protection: Refresh live market data and revalidate ---
    try:
        fresh_price = get_latest_price(symbol)
    except Exception as e:
        log.append(f"[ExecutionAgent] Failed to fetch fresh live quote for {symbol}: {e}")
        return {"execution_result": {"status": "aborted", "error": "Could not fetch fresh live quote"}, "log": log}

    proposed_entry = trade.get("entry_price", 0)
    if proposed_entry > 0:
        price_drift = abs(fresh_price - proposed_entry) / proposed_entry
        if price_drift > MAX_PRICE_DRIFT_PCT:
            msg = f"[ExecutionAgent] Aborted: Market price drifted {price_drift*100:.2f}% since approval request (proposed: ${proposed_entry:.2f}, fresh: ${fresh_price:.2f}, limit: {MAX_PRICE_DRIFT_PCT*100:.1f}%)"
            log.append(msg)
            return {"execution_result": {"status": "aborted", "reason": "price_drift_exceeded", "drift_pct": round(price_drift * 100, 2)}, "log": log}

    # Adapt dynamic bracket levels to fresh entry price
    atr = state.get("technical_indicators", {}).get("atr")
    if atr and atr > 0:
        stop_dist = max(fresh_price * 0.01, min(atr * ATR_STOP_MULTIPLIER, fresh_price * 0.08))
        profit_dist = max(fresh_price * 0.02, min(atr * ATR_PROFIT_MULTIPLIER, fresh_price * 0.18))
    else:
        stop_dist = fresh_price * 0.03
        profit_dist = fresh_price * 0.06

    side = trade["side"]
    if side == "buy":
        fresh_stop = round(fresh_price - stop_dist, 2)
        fresh_take_profit = round(fresh_price + profit_dist, 2)
    else:
        fresh_stop = round(fresh_price + stop_dist, 2)
        fresh_take_profit = round(fresh_price - profit_dist, 2)

    existing_qty = portfolio.get("existing_qty", 0.0)

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
            log.append(f"[ExecutionAgent] Closing trade — submitted as plain market order at ${fresh_price:.2f} (no bracket)")
        else:
            order = submit_bracket_order(
                symbol=trade["symbol"],
                qty=trade["qty"],
                side=trade["side"],
                entry_price=fresh_price,
                take_profit_price=fresh_take_profit,
                stop_loss_price=fresh_stop,
            )
            log.append(f"[ExecutionAgent] Bracket order submitted: entry=${fresh_price:.2f}, SL=${fresh_stop:.2f}, TP=${fresh_take_profit:.2f}")

        result = {
            "status": "submitted",
            "order_id": str(order.id),
            "symbol": trade["symbol"],
            "qty": trade["qty"],
            "side": trade["side"],
            "entry_price": fresh_price,
            "stop_loss_price": fresh_stop,
            "take_profit_price": fresh_take_profit,
            "type": "closing_market_order" if is_closing_trade else "bracket_entry",
        }
        log.append(f"[ExecutionAgent] Order details: {result}")
    except Exception as e:
        result = {"status": "error", "error": str(e)}
        log.append(f"[ExecutionAgent] Order failed: {e}")

    return {"execution_result": result, "log": log}