from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator

class PortfolioState(TypedDict, total=False):
    symbol: str
    market_data: Dict[str, Any]
    technical_indicators: Dict[str, Any]
    technical_analysis: Dict[str, Any]
    fundamental_analysis: Dict[str, Any]
    news_analysis: Dict[str, Any]
    analysis: Dict[str, Any]
    portfolio: Dict[str, Any]
    risk_check: Dict[str, Any]
    proposed_trade: Dict[str, Any]
    approval_status: Optional[str]
    execution_result: Optional[Dict[str, Any]]
    log: Annotated[List[str], operator.add]   # merges lists from parallel branches instead of conflicting