"""Runs inside Hermes' own environment. Proves the installed Hermes runtime dispatches governed
tool calls through the Redline plugin. Equity is a fixture here; mainnet is Phase 1.
    REDLINE_HOME=/tmp/rl ~/.hermes/hermes-agent/venv/bin/python tests/hermes_integration.py
"""
import os, sys, types
HERMES = os.path.expanduser("~/.hermes/hermes-agent")
sys.path.insert(0, HERMES); os.chdir(HERMES)
import hermes_cli.plugins as P

P.discover_plugins(force=True)
lp = P.get_plugin_manager()._plugins.get("redline")
assert lp and isinstance(lp.module, types.ModuleType), "Hermes did not load the redline plugin"
mod = lp.module
mod.configure(equity_reader=lambda: 100.0, price_reader=lambda s: {"SOL": 200.0, "ETH": 4000.0}.get(s))
kw = dict(task_id="probe", session_id="s", turn_id="t", tool_call_id="c")

over, _ = P._dispatch_pre_tool_call_hooks("mcp_clawpump_perps_order_execute", {"market": "SOL-PERP", "size": 0.5}, **kw)
ok, _ = P._dispatch_pre_tool_call_hooks("mcp_clawpump_perps_order_execute", {"market": "SOL-PERP", "size": 0.04}, **kw)
ro, _ = P._dispatch_pre_tool_call_hooks("mcp_clawpump_get_portfolio", {}, **kw)
mod.configure(equity_reader=lambda: (_ for _ in ()).throw(RuntimeError("rpc down")))
down, _ = P._dispatch_pre_tool_call_hooks("mcp_clawpump_swap_execute", {"input_token": "SOL", "amount": 0.001}, **kw)

assert over and "trade_cap" in over, over
assert ok is None and ro is None, (ok, ro)
assert down and "equity" in down, down
print("PASS: over-cap refused | in-policy allowed | read-only untouched | rpc-down fails closed")
