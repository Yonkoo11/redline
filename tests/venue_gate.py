"""Phase 1, venue half: the same policy in front of the LIVE ClawPump MCP.

Three things happen, in order:
  1. equity is read live from the agent wallet; if it cannot be read, nothing else runs
  2. an over-cap swap is dispatched through the Hermes hook and must be REFUSED, with the
     refusal posted to Solana as a memo
  3. an in-policy swap is dispatched and must be ALLOWED, then actually sent to the venue

Step 3 spends real money. It runs ONLY with --execute. Without the flag the script stops after
proving the venue accepts the order (a real quote from Jupiter through the ClawPump MCP) and
prints the exact command that would fire it.

  ~/.hermes/hermes-agent/venv/bin/python tests/venue_gate.py
  ~/.hermes/hermes-agent/venv/bin/python tests/venue_gate.py --execute
"""
import json, os, subprocess, sys, uuid

HERMES = os.path.expanduser("~/.hermes/hermes-agent")
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTE = "--execute" in sys.argv


def mcp(tool, args):
    """One MCP call through @clawpump/agents. Returns the parsed tool result."""
    out = subprocess.run(
        ["node", os.path.join(PROJECT, "probe", "mcp_call.mjs"), "call", tool, json.dumps(args)],
        capture_output=True, text=True, timeout=120, cwd=PROJECT)
    if out.returncode != 0:
        raise RuntimeError(f"{tool} failed: {out.stderr[:300]}")
    env = json.loads(out.stdout)
    if "error" in env:
        raise RuntimeError(f"{tool} error: {env['error']}")
    return json.loads(env["result"]["content"][0]["text"])


if not os.environ.get("REDLINE_OPERATOR_PUBKEY"):
    sys.exit("REDLINE_OPERATOR_PUBKEY is not set, so no policy can verify and every call would be\n"
             "refused as unsigned. Run:  python -m redline.sign keygen   then export the key it prints.")

sys.path.insert(0, HERMES)
os.chdir(HERMES)
import hermes_cli.plugins as P

P.discover_plugins(force=True)
mod = P.get_plugin_manager()._plugins["redline"].module
mod.runtime.wire()

eq = mod._equity()
print(f"1. live equity from the agent wallet: ${eq:.2f}")
assert eq and eq > 0, "equity unreadable; aborting before anything is spent"

sol = mod.runtime.price_usd("SOL")
cap = eq * 0.10
print(f"   SOL ${sol:.2f} | per-order cap ${cap:.2f} (10% of equity)")

kw = dict(task_id="venue", session_id="phase1", turn_id="t1", tool_call_id="c1")
LAMPORTS = 10 ** 9

# ---- 2. over-cap swap must be refused -------------------------------------
over_lamports = int((eq * 0.90) / sol * LAMPORTS)
msg, _ = P._dispatch_pre_tool_call_hooks(
    "mcp_clawpump_swap_execute",
    {"input_mint": "SOL", "output_mint": "USDC", "amount": str(over_lamports)}, **kw)
print(f"\n2. over-cap swap ({over_lamports/LAMPORTS:.4f} SOL, ~${eq*0.90:.2f}) -> {msg}")
assert msg, "an order at 90% of equity must be refused"
if "trade_cap" not in msg:
    # Something stopped it before the size check. That is still a refusal, but it is not the one
    # this gate exists to prove, and the in-policy order below will be refused too.
    print("\n   NOTE: a different rule fired first, so the per-order cap was never reached.")
    print("   Inspect the window with:  python -m redline.day")
    sys.exit(1)

rec = json.loads(open(os.path.expanduser("~/.hermes/redline/tape.jsonl")).readlines()[-1])
print(f"   record hash : {rec['hash']}")
print(f"   memo        : {rec.get('memo_sig') or 'NOT POSTED: ' + str(rec.get('memo_error'))}")
if rec.get("memo_sig"):
    print(f"   solscan     : https://solscan.io/tx/{rec['memo_sig']}")

# ---- 3. in-policy swap must be allowed, then actually sent -----------------
in_lamports = int((eq * 0.05) / sol * LAMPORTS)
verdict, _ = P._dispatch_pre_tool_call_hooks(
    "mcp_clawpump_swap_execute",
    {"input_mint": "SOL", "output_mint": "USDC", "amount": str(in_lamports)}, **kw)
print(f"\n3. in-policy swap ({in_lamports/LAMPORTS:.4f} SOL, ~${eq*0.05:.2f}) -> "
      f"{'ALLOWED' if verdict is None else 'UNEXPECTEDLY REFUSED: ' + str(verdict)}")
assert verdict is None, "a swap at 5% of equity must pass a 10% cap"

quote = mcp("swap_quote", {"input_mint": "SOL", "output_mint": "USDC",
                           "amount": str(in_lamports), "slippage_bps": 50})
print(f"   venue quote : {quote['input']['amount']} SOL -> {quote['output']['amount']} USDC "
      f"via {'/'.join(quote['route'])}, impact {quote['priceImpactPct']}%")

if not EXECUTE:
    print("\nSTOPPED before spending. The refusal half is proven against the live venue and the")
    print("allowed order is priced by the venue. To actually fill it, run:")
    print("  ~/.hermes/hermes-agent/venv/bin/python tests/venue_gate.py --execute")
    sys.exit(0)

fill = mcp("swap_execute", {"input_mint": "SOL", "output_mint": "USDC",
                            "amount": str(in_lamports), "slippage_bps": 50})


def find_sig(node):
    """Any base58 string the right length to be a Solana signature, anywhere in the response.

    The venue does not document where it puts the signature and it was not under the three names
    this script used to try, so the whole structure gets walked instead of guessed at.
    """
    B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    if isinstance(node, str):
        return node if 80 <= len(node) <= 100 and set(node) <= B58 else None
    if isinstance(node, dict):
        node = node.values()
    if isinstance(node, (list, tuple)) or hasattr(node, "__iter__"):
        for v in node:
            found = find_sig(v)
            if found:
                return found
    return None


got = fill.get("output", {}).get("amount")
print(f"\n   FILLED      : {fill.get('status', '?')} on {fill.get('venue', '?')}, "
      f"{quote['input']['amount']} SOL -> {got} USDC")
sig = find_sig(fill)
if sig:
    print(f"   solscan     : https://solscan.io/tx/{sig}")
else:
    print("   solscan     : the venue returned no signature; the fill is the newest transaction")
    print("                 on the agent wallet, readable at")
    print("                 https://solscan.io/account/" + mod.equity.AGENT)
print("\nPhase 1 gate: both halves done on mainnet.")
