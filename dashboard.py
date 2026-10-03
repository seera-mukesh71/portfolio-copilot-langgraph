# dashboard.py
import uuid
import streamlit as st
from langgraph.types import Command

from graph import build_graph
from config import WATCHLIST
from memory import store_decision, get_recent_decisions, reconcile_past_trades
from alpaca_client import get_account, get_positions, get_open_orders, cancel_order, cancel_all_orders

st.set_page_config(page_title="Portfolio Copilot", layout="wide")

# --- Session state setup ---
if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "pending" not in st.session_state:
    st.session_state.pending = {}  # symbol -> {"thread_id": ..., "interrupt_data": ...}
if "results" not in st.session_state:
    st.session_state.results = {}  # symbol -> final result dict

graph = st.session_state.graph

st.title("📊 Personal Portfolio Copilot")
st.caption("LangGraph (SqliteSaver) + Groq + Alpaca (Paper) + Weaviate Memory (P&L Feedback) + ATR Adaptive Risk")

# --- Account snapshot ---
col1, col2, col3 = st.columns(3)
try:
    account = get_account()
    col1.metric("Equity", f"${float(account.equity):,.2f}")
    col2.metric("Cash", f"${float(account.cash):,.2f}")
    col3.metric("Buying Power", f"${float(account.buying_power):,.2f}")
except Exception as e:
    st.error(f"Could not load account info: {e}")

st.divider()

# --- Run controls ---
st.subheader("Run Analysis")
selected_symbols = st.multiselect("Symbols to analyze", WATCHLIST, default=WATCHLIST)

col_run, col_rec = st.columns([2, 1])
if col_run.button("▶ Run Copilot", type="primary"):
    with st.spinner("Reconciling past trades and running agents..."):
        try:
            reconcile_past_trades()
        except Exception as e:
            st.warning(f"Reconciliation note: {e}")

        for symbol in selected_symbols:
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            initial_state = {"symbol": symbol, "log": []}

            try:
                result = graph.invoke(initial_state, config=config)
            except Exception as e:
                st.session_state.results[symbol] = {"error": str(e)}
                continue

            if "__interrupt__" in result:
                interrupt_data = result["__interrupt__"][0].value
                st.session_state.pending[symbol] = {
                    "thread_id": thread_id,
                    "config": config,
                    "interrupt_data": interrupt_data,
                }
            else:
                st.session_state.results[symbol] = result
                try:
                    store_decision(result)
                except Exception as e:
                    st.warning(f"Could not store memory for {symbol}: {e}")

if col_rec.button("🔄 Sync P&L / Reconcile Orders"):
    try:
        reconcile_past_trades()
        st.success("Reconciliation complete! Updated trade outcomes with Alpaca fills.")
    except Exception as e:
        st.error(f"Reconciliation error: {e}")

st.divider()

# --- Pending approvals ---
if st.session_state.pending:
    st.subheader("🔔 Trades Awaiting Approval")

    for symbol in list(st.session_state.pending.keys()):
        entry = st.session_state.pending[symbol]
        trade = entry["interrupt_data"]["proposed_trade"]

        with st.container(border=True):
            st.markdown(f"### {symbol} — {trade['side'].upper()}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Qty", trade["qty"])
            c2.metric("Entry", f"${trade['entry_price']:.2f}")
            c3.metric("Stop Loss", f"${trade['stop_loss_price']:.2f}")
            c4.metric("Take Profit", f"${trade['take_profit_price']:.2f}")
            st.write(f"**Rationale:** {trade['rationale']}")
            st.write(f"**Confidence:** {trade['confidence']}")

            b1, b2 = st.columns(2)

            if b1.button(f"✅ Approve {symbol}", key=f"approve_{symbol}"):
                try:
                    final_result = graph.invoke(
                        Command(resume="approved"), config=entry["config"]
                    )
                    st.session_state.results[symbol] = final_result
                    del st.session_state.pending[symbol]
                    try:
                        store_decision(final_result)
                    except Exception as e:
                        st.warning(f"Could not store memory for {symbol}: {e}")
                    st.success(f"{symbol} trade approved and processed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Approval failed for {symbol}: {e}")

            if b2.button(f"❌ Reject {symbol}", key=f"reject_{symbol}"):
                try:
                    final_result = graph.invoke(
                        Command(resume="rejected"), config=entry["config"]
                    )
                    st.session_state.results[symbol] = final_result
                    del st.session_state.pending[symbol]
                    try:
                        store_decision(final_result)
                    except Exception as e:
                        st.warning(f"Could not store memory for {symbol}: {e}")
                    st.success(f"{symbol} trade rejected.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Rejection failed for {symbol}: {e}")

st.divider()

# --- Results ---
if st.session_state.results:
    st.subheader("📋 Run Results")
    for symbol, result in st.session_state.results.items():
        with st.expander(f"{symbol}", expanded=False):
            if "error" in result:
                st.error(result["error"])
                continue

            execution_result = result.get("execution_result")
            if execution_result:
                st.json(execution_result)
            else:
                st.info("No trade executed for this symbol.")

            st.write("**Log trail:**")
            for line in result.get("log", []):
                st.text(line)

st.divider()

# --- Memory browser ---
st.subheader("🧠 Recent Memory & P&L Feedback (per symbol)")
mem_symbol = st.selectbox("View past decisions for", WATCHLIST)
if st.button("Load memory"):
    try:
        decisions = get_recent_decisions(mem_symbol, limit=10)
        if decisions:
            st.dataframe(decisions, use_container_width=True)
        else:
            st.info("No past decisions stored yet for this symbol.")
    except Exception as e:
        st.error(f"Could not load memory: {e}")

# --- Current positions ---
st.subheader("💼 Current Positions")
try:
    positions = get_positions()
    if positions:
        rows = [
            {
                "Symbol": p.symbol,
                "Qty": p.qty,
                "Side": p.side,
                "Avg Entry": p.avg_entry_price,
                "Market Value": p.market_value,
                "Unrealized P/L": p.unrealized_pl,
            }
            for p in positions
        ]
        st.table(rows)
    else:
        st.info("No open positions.")
except Exception as e:
    st.error(f"Could not load positions: {e}")

st.divider()

# --- Open orders management ---
st.subheader("🧾 Open Orders")

try:
    open_orders = get_open_orders()
except Exception as e:
    open_orders = []
    st.error(f"Could not load open orders: {e}")

if open_orders:
    if st.button("🗑️ Cancel ALL open orders", type="secondary"):
        try:
            cancel_all_orders()
            st.success("All open orders cancelled.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not cancel all orders: {e}")

    st.write(f"**{len(open_orders)} open order(s):**")

    for order in open_orders:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 2, 1])
            c1.write(f"**{order.symbol}**")
            c2.write(order.side.value.upper())
            c3.write(f"Qty: {order.qty}")
            c4.write(f"Submitted: {order.submitted_at.strftime('%b %d, %I:%M %p')}")
            if c5.button("Cancel", key=f"cancel_{order.id}"):
                try:
                    cancel_order(str(order.id))
                    st.success(f"Cancelled {order.symbol} order.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not cancel order: {e}")
else:
    st.info("No open orders.")