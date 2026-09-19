"""Read the log in a terminal.

The site has a page that reads this same file in a browser, and it is nicer. This exists because
the file on your machine is the truth, and a tool whose evidence can only be read through a website
is a tool that asks you to trust the website. Everything the page does, this does.

  redline log                     the last 20 decisions
  redline log -n 100              more of them
  redline log --refused           only what was stopped
  redline log --watched           only what would have been stopped
  redline log --rule trade_cap    one rule
  redline log --today             since 00:00 UTC
  redline log --raw               the records themselves, one per line
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

C = {"red": "\033[31m", "dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m"}
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    C = {k: "" for k in C}


def tape_path() -> Path:
    from . import HOME

    return Path(os.environ.get("REDLINE_TAPE", HOME / "tape.jsonl"))


def load(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass          # a half-written last line is normal while an agent is running
    return out


def verdict(r: dict) -> str:
    if r.get("would_refuse"):
        return "watched"
    if str(r.get("tool", "")).startswith("operator:"):
        return "operator"
    return "allowed" if r.get("allowed") else "refused"


def render(r: dict) -> str:
    v = verdict(r)
    tag = {"refused": f"{C['red']}REFUSED {C['off']}",
           "watched": f"{C['dim']}WATCHED {C['off']}",
           "operator": f"{C['bold']}OPERATOR{C['off']}",
           "allowed": f"{C['dim']}allowed {C['off']}"}[v]
    when = time.strftime("%m-%d %H:%M", time.gmtime(r.get("ts", 0)))
    intent = r.get("intent") or {}
    kind = str(intent.get("kind") or "")
    what = " ".join(x for x in (kind, intent.get("market") or "",
                                f"${intent['notional_usd']:.2f}" if intent.get("notional_usd") else "") if x)
    eq = f"{C['dim']}eq ${r['equity_usd']:.2f}{C['off']}" if r.get("equity_usd") is not None else ""
    receipt = f"{C['dim']}{r['memo_sig'][:12]}…{C['off']}" if r.get("memo_sig") else ""
    line = f"{C['dim']}{when}{C['off']}  {tag}  {what:<22} {eq}  {receipt}"
    return line + f"\n          {C['dim']}{r.get('reason','')}{C['off']}"


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0

    path = tape_path()
    rows = load(path)
    if not rows:
        print(f"no records at {path}")
        print("nothing has been judged yet, or the agent writes somewhere else (REDLINE_TAPE).")
        return 0

    if "--refused" in args:
        rows = [r for r in rows if verdict(r) == "refused"]
    if "--watched" in args:
        rows = [r for r in rows if verdict(r) == "watched"]
    if "--rule" in args:
        want = args[args.index("--rule") + 1]
        rows = [r for r in rows if r.get("rule") == want]
    if "--today" in args:
        start = time.mktime(time.strptime(time.strftime("%Y-%m-%d", time.gmtime()), "%Y-%m-%d"))
        start -= time.timezone
        rows = [r for r in rows if r.get("ts", 0) >= start]

    n = 20
    if "-n" in args:
        n = int(args[args.index("-n") + 1])
    shown = rows[-n:]

    if "--raw" in args:
        for r in shown:
            print(json.dumps(r, sort_keys=True))
        return 0

    for r in shown:
        print(render(r))

    counts = {}
    for r in rows:
        counts[verdict(r)] = counts.get(verdict(r), 0) + 1
    tally = "  ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    print(f"\n{C['dim']}showing {len(shown)} of {len(rows)} · {tally} · {path}{C['off']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
