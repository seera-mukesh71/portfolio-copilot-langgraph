# agents/decision_agent.py
from state import PortfolioState


def decision_node(state: PortfolioState) -> PortfolioState:
    """
    Synthesizes analysis + risk check into a single proposed trade object.
    This is the artifact that gets shown to the human for approval.
    """
    symbol = state["symbol"]
    analysis = state["analysis"]
    risk_check = state["risk_check"]

    proposed_trade = {
        "symbol": symbol,
        "side": risk_check["side"],
        "qty": risk_check["qty"],
        "entry_price": risk_check["entry_price"],
        "stop_loss_price": risk_check["stop_loss_price"],
        "take_profit_price": risk_check["take_profit_price"],
        "rationale": analysis.get("rationale", ""),
        "confidence": analysis.get("confidence", 0.0),
    }

    log = [f"[DecisionAgent] proposed_trade={proposed_trade}"]
    return {"proposed_trade": proposed_trade, "approval_status": "pending", "log": log}