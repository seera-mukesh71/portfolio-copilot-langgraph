# graph.py
import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt

from state import PortfolioState
from agents.market_data_agent import market_data_node
from agents.technical_agent import technical_node
from agents.fundamental_agent import fundamental_node
from agents.news_agent import news_node
from agents.synthesis_agent import synthesis_node
from agents.portfolio_agent import portfolio_node
from agents.risk_agent import risk_node
from agents.decision_agent import decision_node
from agents.execution_agent import execution_node

_conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(_conn)


def risk_gate(state: PortfolioState) -> str:
    if state["risk_check"]["passed"]:
        return "decision"
    return "rejected"


def human_approval_node(state: PortfolioState) -> PortfolioState:
    decision = interrupt({
        "message": "Review this proposed trade and approve or reject it.",
        "proposed_trade": state["proposed_trade"],
    })
    log = [f"[HumanApproval] decision={decision}"]
    return {"approval_status": decision, "log": log}


def approval_gate(state: PortfolioState) -> str:
    if state.get("approval_status") == "approved":
        return "execute"
    return "rejected"


def build_graph():
    builder = StateGraph(PortfolioState)

    builder.add_node("market_data", market_data_node)
    builder.add_node("technical", technical_node)
    builder.add_node("fundamental", fundamental_node)
    builder.add_node("news", news_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("portfolio", portfolio_node)
    builder.add_node("risk", risk_node)
    builder.add_node("decision", decision_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("execute", execution_node)

    builder.set_entry_point("market_data")

    # Market data feeds all three specialist agents in parallel
    builder.add_edge("market_data", "technical")
    builder.add_edge("market_data", "fundamental")
    builder.add_edge("market_data", "news")

    # All three must complete before synthesis runs
    builder.add_edge("technical", "synthesis")
    builder.add_edge("fundamental", "synthesis")
    builder.add_edge("news", "synthesis")

    builder.add_edge("synthesis", "portfolio")
    builder.add_edge("portfolio", "risk")

    builder.add_conditional_edges("risk", risk_gate, {"decision": "decision", "rejected": END})
    builder.add_edge("decision", "human_approval")
    builder.add_conditional_edges("human_approval", approval_gate, {"execute": "execute", "rejected": END})
    builder.add_edge("execute", END)

    return builder.compile(checkpointer=checkpointer)