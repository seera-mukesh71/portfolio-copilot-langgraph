# agents/risk_agent.py
from state import PortfolioState
from config import MAX_POSITION_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT
from alpaca_client import get_latest_price


def risk_node(state: PortfolioState) -> PortfolioState:
    analysis = state["analysis"]
    portfolio = state["portfolio"]
    symbol = state["symbol"]

    view = analysis.get("view", "neutral")
    confidence = analysis.get("confidence", 0.0)
    equity = portfolio["equity"]

    existing_qty = portfolio.get("existing_qty", 0.0)  # negative = short, positive = long
    pending_qty = portfolio.get("pending_qty", 0.0)
    total_exposure_qty = existing_qty + pending_qty  # combined filled + queued

    passed = True
    reasons = []

    if view == "neutral":
        passed = False
        reasons.append("Neutral view — no trade signal")

    if confidence < 0.6:
        passed = False
        reasons.append(f"Confidence too low ({confidence})")

    live_price = get_latest_price(symbol)

    # Sanity check: live quote should be reasonably close to the recent historical close.
    last_close = state["market_data"]["last_close"]

    if last_close > 0:
        deviation = abs(live_price - last_close) / last_close

        if deviation > 0.15:
            passed = False
            reasons.append(
                f"Price sanity check failed: live_price={live_price} vs "
                f"last_close={last_close} ({deviation*100:.1f}% gap) — likely bad quote"
            )

    # Max total shares allowed in this symbol, in either direction
    max_dollar_size = equity * MAX_POSITION_PCT
    max_total_qty = int(max_dollar_size / live_price) if live_price > 0 else 0

    side = (
        "buy" if view == "bullish"
        else "sell" if view == "bearish"
        else None
    )

    # Block trades that would INCREASE exposure in a direction we're already maxed on
    same_direction = (
        (side == "buy" and total_exposure_qty > 0) or
        (side == "sell" and total_exposure_qty < 0)
    )

    current_exposure = abs(total_exposure_qty)

    if same_direction and current_exposure >= max_total_qty:
        passed = False
        reasons.append(
            f"Already at/above max exposure for this symbol "
            f"({current_exposure} shares including pending, cap {max_total_qty})"
        )
        qty = 0

    elif same_direction:
        # Only allow enough additional qty to reach the cap
        qty = max_total_qty - current_exposure

    else:
        # Opposite direction or no position — normal full sizing
        qty = max_total_qty

    if qty <= 0:
        passed = False
        reasons.append("Computed quantity is zero or invalid")

    if view == "bullish":
        stop_loss_price = live_price * (1 - STOP_LOSS_PCT)
        take_profit_price = live_price * (1 + TAKE_PROFIT_PCT)

    elif view == "bearish":
        stop_loss_price = live_price * (1 + STOP_LOSS_PCT)
        take_profit_price = live_price * (1 - TAKE_PROFIT_PCT)

    else:
        stop_loss_price = None
        take_profit_price = None

    risk_check = {
        "passed": passed,
        "reasons": reasons,
        "side": side,
        "qty": qty,
        "entry_price": live_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
    }

    log = [f"[RiskAgent] passed={passed} side={side} qty={qty} live_price={live_price} existing_qty={existing_qty} pending_qty={pending_qty} total_exposure_qty={total_exposure_qty} reasons={reasons}"]
    return {"risk_check": risk_check, "log": log}