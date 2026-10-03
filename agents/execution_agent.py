# agents/execution_agent.py
from alpaca_client import (
    submit_bracket_order,
    submit_market_order,
    get_latest_price,
    get_account,
    get_positions,
    get_open_orders,
)
from config import (
    MAX_POSITION_PCT,
    MAX_PRICE_DRIFT_PCT,
    ATR_STOP_MULTIPLIER,
    ATR_PROFIT_MULTIPLIER,
)
from state import PortfolioState


def execution_node(state: PortfolioState) -> PortfolioState:
    trade = state["proposed_trade"]
    portfolio = state["portfolio"]
    log = []
    symbol = trade["symbol"]
    side = trade["side"]

    if state.get("approval_status") != "approved":
        log.append("[ExecutionAgent] Skipped — trade not approved")
        return {"execution_result": {"status": "skipped"}, "log": log}

    # --- 1. Stale Price Protection: Refresh live market quote and check drift ---
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

    # --- 2. Live Exposure Re-Validation: Re-check portfolio exposure limits right before submission ---
    try:
        fresh_account = get_account()
        fresh_positions = get_positions()
        fresh_open_orders = get_open_orders(symbol=symbol)

        fresh_equity = float(fresh_account.equity)
        fresh_pos = next((p for p in fresh_positions if p.symbol == symbol), None)
        fresh_existing_qty = float(fresh_pos.qty) if fresh_pos else 0.0
        fresh_pending_qty = sum(
            float(o.qty) if o.side.value == "buy" else -float(o.qty)
            for o in fresh_open_orders
        )
        fresh_total_exposure = fresh_existing_qty + fresh_pending_qty

        max_dollar_size = fresh_equity * MAX_POSITION_PCT
        max_total_qty = int(max_dollar_size / fresh_price) if fresh_price > 0 else 0

        same_direction = (
            (side == "buy" and fresh_total_exposure > 0) or
            (side == "sell" and fresh_total_exposure < 0)
        )

        exec_qty = int(trade["qty"])

        if same_direction and abs(fresh_total_exposure) >= max_total_qty:
            msg = f"[ExecutionAgent] Aborted: Exposure cap reached between proposal and execution (current exposure: {abs(fresh_total_exposure)} shares, cap {max_total_qty})"
            log.append(msg)
            return {"execution_result": {"status": "aborted", "reason": "exposure_cap_exceeded"}, "log": log}

        elif same_direction:
            available_capacity = max_total_qty - abs(fresh_total_exposure)
            if available_capacity < exec_qty:
                log.append(f"[ExecutionAgent] Adjusted order quantity from {exec_qty} to {available_capacity} to stay within {MAX_POSITION_PCT*100:.0f}% exposure limit")
                exec_qty = available_capacity

        if exec_qty <= 0:
            log.append("[ExecutionAgent] Aborted: Computed executable quantity is zero")
            return {"execution_result": {"status": "aborted", "reason": "zero_quantity"}, "log": log}

    except Exception as e:
        log.append(f"[ExecutionAgent] Exposure re-validation check warning: {e}")
        exec_qty = trade["qty"]
        fresh_existing_qty = portfolio.get("existing_qty", 0.0)

    # --- 3. Adapt dynamic bracket levels to fresh entry price ---
    atr = state.get("technical_indicators", {}).get("atr")
    if atr and atr > 0:
        stop_dist = max(fresh_price * 0.01, min(atr * ATR_STOP_MULTIPLIER, fresh_price * 0.08))
        profit_dist = max(fresh_price * 0.02, min(atr * ATR_PROFIT_MULTIPLIER, fresh_price * 0.18))
    else:
        stop_dist = fresh_price * 0.03
        profit_dist = fresh_price * 0.06

    if side == "buy":
        fresh_stop = round(fresh_price - stop_dist, 2)
        fresh_take_profit = round(fresh_price + profit_dist, 2)
    else:
        fresh_stop = round(fresh_price + stop_dist, 2)
        fresh_take_profit = round(fresh_price - profit_dist, 2)

    # Check if closing trade
    is_closing_trade = (
        (side == "buy" and fresh_existing_qty < 0) or
        (side == "sell" and fresh_existing_qty > 0)
    )

    try:
        if is_closing_trade:
            order = submit_market_order(
                symbol=trade["symbol"],
                qty=exec_qty,
                side=trade["side"],
            )
            log.append(f"[ExecutionAgent] Closing trade — submitted as plain market order at ${fresh_price:.2f} (no bracket)")
        else:
            order = submit_bracket_order(
                symbol=trade["symbol"],
                qty=exec_qty,
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
            "qty": exec_qty,
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