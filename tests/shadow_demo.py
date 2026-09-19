"""Run one over-cap order in shadow mode against live equity, so the tape carries a real
example of what watching looks like before enforcing. Nothing is sent to a venue.

  REDLINE_MODE=shadow ~/.hermes/hermes-agent/venv/bin/python tests/shadow_demo.py
"""
import json, os, sys

if os.environ.get("REDLINE_MODE") != "shadow":
    sys.exit("run with REDLINE_MODE=shadow")
if not os.environ.get("REDLINE_OPERATOR_PUBKEY"):
    sys.exit("REDLINE_OPERATOR_PUBKEY is not set")

HERMES = os.path.expanduser("~/.hermes/hermes-agent")
sys.path.insert(0, HERMES); os.chdir(HERMES)
import hermes_cli.plugins as P

P.discover_plugins(force=True)
mod = P.get_plugin_manager()._plugins["redline"].module
mod.runtime.wire()
eq = mod._equity()
sol = mod.runtime.price_usd("SOL")
lam = int((eq * 0.60) / sol * 10 ** 9)

out, _ = P._dispatch_pre_tool_call_hooks(
    "mcp_clawpump_swap_execute",
    {"input_mint": "SOL", "output_mint": "USDC", "amount": str(lam)},
    task_id="shadow", session_id="shadow", turn_id="t1", tool_call_id="c1")
rec = json.loads(open(os.path.expanduser("~/.hermes/redline/tape.jsonl")).readlines()[-1])
print(f"equity ${eq:.2f}, order ~${eq*0.60:.2f}")
print("hook returned:", "allowed through (shadow)" if out is None else out)
print("recorded     :", rec["mode"], "| would_refuse:", rec.get("would_refuse"), "|", rec["rule"])
assert out is None and rec.get("would_refuse") and rec["mode"] == "shadow"
print("\nShadow mode: the order was judged and let through, and the verdict is on the tape.")
