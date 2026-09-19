"""Phase 1, refusal half: a real over-cap order dispatched through the installed Hermes runtime,
judged against LIVE equity read from the ClawPump agent wallet, refused, and the refusal posted to
Solana mainnet. Run:  ~/.hermes/hermes-agent/venv/bin/python tests/mainnet_gate.py
"""
import os, sys, types, json
HERMES = os.path.expanduser("~/.hermes/hermes-agent")
sys.path.insert(0, HERMES); os.chdir(HERMES)
import hermes_cli.plugins as P

P.discover_plugins(force=True)
mod = P.get_plugin_manager()._plugins["redline"].module
mod.runtime.wire()                      # live equity + live price + mainnet tape
eq = mod._equity()
print(f"live equity read from the agent wallet: ${eq:.2f}")
assert eq and eq > 0, "equity unreadable; aborting before spending anything"

kw = dict(task_id="gate", session_id="phase1", turn_id="t1", tool_call_id="c1")

ok, _ = P._dispatch_pre_tool_call_hooks(
    "mcp_clawpump_perps_order_execute",
    {"market": "SOL-PERP", "size": round((eq * 0.05) / mod.runtime.price_usd("SOL"), 4), "leverage": 1}, **kw)
print("in-policy order:", "allowed" if ok is None else f"UNEXPECTEDLY REFUSED: {ok}")
assert ok is None, "an order at 5% of equity must pass a 10% cap"

over_size = round((eq * 0.9) / mod.runtime.price_usd("SOL"), 4)     # ~90% of equity: far over the 10% cap
msg, _ = P._dispatch_pre_tool_call_hooks(
    "mcp_clawpump_perps_order_execute", {"market": "SOL-PERP", "size": over_size, "leverage": 1}, **kw)
print("verdict:", msg)
assert msg and "trade_cap" in msg, "expected a trade_cap refusal"

tape = json.loads(open(os.path.expanduser("~/.hermes/redline/tape.jsonl")).readlines()[-1])
print("record hash:", tape["hash"])
print("memo signature:", tape.get("memo_sig") or f"NOT POSTED: {tape.get('memo_error')}")
print("solscan:", f"https://solscan.io/tx/{tape.get('memo_sig')}" if tape.get("memo_sig") else "n/a")
