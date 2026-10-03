# main.py
import uuid
from langgraph.types import Command
from graph import build_graph
from config import WATCHLIST
from memory import store_decision, close_client, reconcile_past_trades


def run_for_symbol(graph, symbol: str):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {"symbol": symbol, "log": []}

    print(f"\n=== Running copilot for {symbol} ===")
    result = graph.invoke(initial_state, config=config)

    if "__interrupt__" in result:
        interrupt_data = result["__interrupt__"][0].value
        print("\n--- HUMAN APPROVAL REQUIRED ---")
        print(f"Symbol: {symbol}")
        print(f"Proposed trade: {interrupt_data['proposed_trade']}")

        decision = input("Approve this trade? (yes/no) [default: no]: ").strip().lower()
        resume_value = "approved" if decision == "yes" else "rejected"

        final_result = graph.invoke(Command(resume=resume_value), config=config)
        print(f"Execution result: {final_result.get('execution_result')}")
        print("Log trail:")
        for line in final_result.get("log", []):
            print(f"  {line}")

        try:
            store_decision(final_result)
        except Exception as e:
            print(f"[WARN] Could not store decision to memory: {e}")
    else:
        print("No trade proposed (risk check failed or neutral view).")
        print("Log trail:")
        for line in result.get("log", []):
            print(f"  {line}")

        try:
            store_decision(result)
        except Exception as e:
            print(f"[WARN] Could not store decision to memory: {e}")


if __name__ == "__main__":
    graph = build_graph()
    try:
        print("[INFO] Reconciling closed trades and updating memory with realized P&L...")
        reconcile_past_trades()
        for symbol in WATCHLIST:
            try:
                run_for_symbol(graph, symbol)
            except Exception as e:
                print(f"[ERROR] Run failed for {symbol}: {e}")
    finally:
        close_client()