from tools.search import search, clear_query_ledger, get_query_ledger
from tools.reader import read_doc
from tools.trade import get_trade_series
from tools.calculator import compute_change

__all__ = [
    "search",
    "read_doc",
    "get_trade_series",
    "compute_change",
    "clear_query_ledger",
    "get_query_ledger",
    "execute_tool"
]

def execute_tool(name: str, **kwargs):
    """
    Unified dispatcher to invoke any of the four deterministic courtroom tools.
    """
    tool_map = {
        "search": search,
        "read_doc": read_doc,
        "get_trade_series": get_trade_series,
        "compute_change": compute_change,
    }
    func = tool_map.get(name.lower().strip())
    if not func:
        raise ValueError(f"Unknown tool '{name}'. Available tools: {list(tool_map.keys())}")
    return func(**kwargs)
