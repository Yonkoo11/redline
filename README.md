<div align="center">

# Redline

![refusal tests](https://img.shields.io/badge/refusal_tests-20%2F20_passing-3fb950)
[![tests](https://github.com/Yonkoo11/redline/actions/workflows/tests.yml/badge.svg)](https://github.com/Yonkoo11/redline/actions/workflows/tests.yml)
![runtime](https://img.shields.io/badge/Hermes_runtime_dispatch-4%2F4_cases_pass-121212)
![tape](https://img.shields.io/badge/on--chain_refusal-mainnet_confirmed-121212)
[![live](https://img.shields.io/badge/live-yonkoo11.github.io%2Fredline-3fb950)](https://yonkoo11.github.io/redline/)

### Kill switch for claw traders.

**Redline is a Hermes plugin that holds a ClawPump trading agent under a policy its operator wrote. Every order the agent tries passes the policy or is refused, and a refusal is written to Solana as a memo carrying the record's hash. Today: 20 tests green, the real Hermes runtime dispatching through it, and a refusal decided from live on-chain equity and recorded on Solana mainnet.**

**[ Live ↗ ](https://yonkoo11.github.io/redline/)** · **[ Verify it yourself ↗ ](#verify-it-yourself-in-60-seconds)** · **[ The receipt ↗ ](https://solscan.io/tx/2pFTPkGoK4y3yPkdMZ5EQd3FYnGjTNv2qwdsoBmkrzGKq2fbvQDq6eGVRQvU2Rx58WF2qfLku5sV7R5YMVZHQe29)** · **[ @useredline ↗ ](https://x.com/useredline)**

Built for The AnsemHack Clawrena (ClawPump × pump.fun, Inference Markets).

</div>

---

## The tape page

*What the still shows: the shell that is live today at [yonkoo11.github.io/redline](https://yonkoo11.github.io/redline/). Policy on the left, an empty tape on the right, and a status line that says no mainnet transaction exists yet.*

| desktop, 1280 wide | phone, 390 wide |
|---|---|
| ![Redline tape page, desktop: policy panel and empty tape](docs/images/landing.png) | ![Redline tape page, phone](docs/images/landing-phone.png) |

## Table of contents
- [The tape page](#the-tape-page)
- [Set it up](#set-it-up)
- [The problem](#the-problem)
- [What Redline is](#what-redline-is)
- [Verify it yourself in 60 seconds](#verify-it-yourself-in-60-seconds)
- [The headline result](#the-headline-result)
- [Architecture](#architecture)
- [The policy](#the-policy)
- [Signing, and what it buys](#signing-and-what-it-buys)
- [Watching before enforcing](#watching-before-enforcing)
- [What's real, and what we deliberately did not claim](#whats-real-and-what-we-deliberately-did-not-claim)
- [Tech stack](#tech-stack)
- [Project layout](#project-layout)
- [Run it locally](#run-it-locally)
- [Tests](#tests)

## Set it up

```bash
hermes plugins install Yonkoo11/redline && hermes plugins enable redline
pip install -r requirements.txt            # cryptography, for the signature check

python -m redline.sign keygen              # once ever; keep this file away from the agent
# build your limits at https://useredline.xyz/policy/ and save them to ~/.hermes/redline/policy.json
python -m redline.sign sign ~/.hermes/redline/policy.json
export REDLINE_OPERATOR_PUBKEY="<the key the last command printed>"

export REDLINE_MODE=shadow                 # judge everything, block nothing, read the log first
```

Four pages, all static, all reading real data: the [tape](https://useredline.xyz/),
the [policy builder](https://useredline.xyz/policy/),
your [own log](https://useredline.xyz/log/) (parsed in your browser, never uploaded),
and the [guide](https://useredline.xyz/guide/) to every reason it can refuse.

## The problem

- **Trading agents carry their risk limits in the prompt.** Of the 200 newest tokens on ClawPump on 2026-09-18, 111 describe a trading agent; the platform itself offers a daily model-spend budget and a wallet-address whitelist, and no per-trade cap, daily loss limit, drawdown halt or leverage limit (clawpump.tech/docs, read 2026-09-18). A limit in a prompt is a suggestion the model can argue with.
- **A safety net that is never exercised fails when it is needed.** On this team's previous agent (Helmsman, BNB Chain, June 2026) the emergency swap failed both times it was the only defence, because it had never been run in isolation.
- **Holders cannot see the limits at all.** Nothing an operator promises about risk is checkable from the outside.

## What Redline is

A plugin that sits between the model and the tools that move money. The loop:

<div align="center">

**`TOOL CALL → INTENT → POLICY → ALLOW | REFUSE → TAPE`**

</div>

1. **Tool call.** Hermes fires `pre_tool_call` before any tool runs. Redline only looks at money-moving ClawPump tools (`perps_order_execute`, `swap_execute`, collateral withdrawals, transfers). Everything else passes untouched.
2. **Intent.** `redline/intent.py` turns the call into a notional in USD, a market, a leverage and a destination. Anything it cannot price becomes `None`, and `None` is refused.
3. **Policy.** `redline/policy.py` applies, in order: halt flag, equity readable, refusal cooldown, drawdown from high-water mark, daily loss, then scope and size. Fails closed on every unknown.
4. **Allow or refuse.** An allowed call proceeds. A refused call returns `{"action": "block", "message": ...}` and the model sees the reason.
5. **Tape.** `redline/tape.py` appends a hashed record to `tape.jsonl`; refusals are also posted to Solana as a memo (`redline:refused:<hash>`) signed by a separate tape wallet.

## Verify it yourself in 60 seconds

No key, no wallet, no chain access needed for the first two checks. Every line below was run before it was written here; the expected results are in the comments.

```bash
git clone https://github.com/Yonkoo11/redline && cd redline
python3 -m unittest discover -s tests -t .          # → Ran 20 tests ... OK
python3 -c "from redline.policy import *; print(evaluate(Policy(), State(), Intent('perp', 12.0, market='SOL'), 100.0, 0).reason)"
                                                    # → notional $12.00 > cap $10.00 (10.0% of equity)
# with Hermes v2026.9.14+ installed and the plugin linked into ~/.hermes/plugins/redline:
~/.hermes/hermes-agent/venv/bin/python tests/hermes_integration.py
                                                    # → PASS: over-cap refused | in-policy allowed | read-only untouched | rpc-down fails closed
hermes plugins validate ./redline                   # → Validation passed.
```

The first check proves the rulebook. The third proves the installed Hermes runtime routes tool calls through it and honours the block. Neither touches a real venue: equity is a fixture in both, and the mainnet gate below is not yet passed.

## The headline result

A refusal decided from **live** equity. Redline read the ClawPump agent wallet on Solana, priced it
through Jupiter, judged a real order against the operator's policy, refused it, and wrote the
refusal to Solana mainnet:

```
live equity read from the agent wallet: $17.02
in-policy order: allowed
verdict: REDLINE refused (trade_cap): notional $15.32 > cap $1.70 (10.0% of equity)
record hash: f1c33a948cd5647515ed32db1aef39b35b709959e340c225c0f63d226297cfd2
```

The memo on chain carries the hash of that record, so the tape cannot be edited after the fact:

```
slot: 448238999 | err: None
memo: redline:refused:f1c33a948cd5647515ed32db1aef39b3
```

[Transaction 2pFTPkGo…HQe29](https://solscan.io/tx/2pFTPkGoK4y3yPkdMZ5EQd3FYnGjTNv2qwdsoBmkrzGKq2fbvQDq6eGVRQvU2Rx58WF2qfLku5sV7R5YMVZHQe29),
tape wallet `61QDPf756rts88PADMZX2TUkqbFmdCfCCvkiwtDSuRHo`, agent wallet
`FT5GaRv2eV74aS3dTPw6ZNsVBackGTW9dNQfw4jSZirz`. Reproduce it with
`~/.hermes/hermes-agent/venv/bin/python tests/mainnet_gate.py`.

Every record says which equity it judged against and whether that equity was live or a test
fixture, because a refusal decided from a made-up balance proves nothing.

## Architecture

```mermaid
flowchart TB
  H[Hermes agent loop] -- pre_tool_call(tool_name, args) --> P[redline/__init__.py]
  P -- intent_from_call --> I[redline/intent.py]
  P -- wallet_equity_usd --> E[redline/equity.py]
  E -- getBalance / getTokenAccountsByOwner --> RPC[(Solana RPC)]
  E -- price/v3 --> J[(Jupiter price)]
  P -- evaluate --> R[redline/policy.py]
  R -- allow --> T[mcp_clawpump_* tool runs]
  R -- refuse --> B["{action: block, message}"]
  P -- write --> W[redline/tape.py]
  W -- solana transfer --with-memo --> M[(Solana memo)]
```

The hook boundary is `redline/__init__.py`; the rulebook is `redline/policy.py`; the two things that touch the outside world are `redline/equity.py` (reads) and `redline/tape.py` (writes).

## The policy

Stored at `~/.hermes/redline/policy.json`. Defaults:

| rule | default | what it does |
|---|---|---|
| `max_trade_pct_equity` | 10 | refuse any order above this share of equity |
| `max_daily_loss_pct` | 5 | refuse new risk once the UTC day is down this much |
| `max_drawdown_pct` | 15 | halt everything once equity is this far under its high-water mark; stays halted until an operator resets |
| `max_leverage` | 2 | refuse above this |
| `allowed_markets` | SOL, ETH | perps outside the list are refused |
| `allowed_tokens` | SOL, USDC | swaps outside the list are refused |
| `allowed_destinations` | none | transfers to anything else are refused |
| collateral withdrawals | always refused | operator-only, by design |
| `refusal_cooldown` | 5 in 30 min | after repeated refusals, refuse everything for the window |
| equity unreadable | refuse | fail closed |
| order unpriceable | refuse | fail closed |
| policy unsigned, altered, or key not pinned | refuse | fail closed |
| policy contains an unknown field | refuse | a misspelled limit is a limit that is not enforced |
| `mode` | `enforce` | `shadow` judges and records without blocking |

## Signing, and what it buys

Without a signature the policy is a plain file in a directory the agent's own process can write, so
an agent able to run shell commands could raise its own ceiling and then trade inside it. Redline
signs the canonical bytes of the policy with Ed25519 and verifies them against a public key pinned
in the environment. A single changed digit invalidates the signature, and an unverified policy
refuses every governed call rather than falling back to a default.

It does **not** protect an operator who keeps the signing key on the machine the agent can read.
It raises the bar from editing a file to stealing a key. Keep the key elsewhere, and back it up.

```bash
python -m redline.sign check ~/.hermes/redline/policy.json
```

The limits published on the site carry their signature, and the operator public key is printed on
the page, so anyone can run that check against the published policy without asking us for anything.

## Watching before enforcing

A policy you have never run should not be the thing standing between an agent and your money on its
first day. `REDLINE_MODE=shadow` judges every order, writes the verdict with `would_refuse: true`,
and blocks nothing. Read a session of that, then enforce the same limits. Watching never consumes
the refusal cool-down, so observing cannot trip a limit that only enforcing should trip.

## What's real, and what we deliberately did not claim

| Capability | Status |
|---|---|
| **Policy engine** | Real. 38 unit tests, `tests/test_policy.py`, run in CI. |
| **Operator signatures** | Real. Ed25519 over the canonical policy; an altered policy refuses everything. `OperatorSignature` and `UnknownFields` in the suite. |
| **Watching before enforcing** | Real. `ShadowMode` in the suite, and one watched order is on the public tape. |
| **ClawPump MCP, live** | Real. Probed with a real key: 132 tools, schemas in `probe/`. `get_portfolio` and `swap_quote` return live data for the agent wallet. |
| **Hermes runtime dispatch** | Real. `tests/hermes_integration.py` passes inside the installed Hermes v0.21.3; `hermes plugins validate` clean. |
| **Refusal on Solana mainnet, from live equity** | Real. Transaction linked above, memo matches the record hash, reproducible with `tests/mainnet_gate.py`. |
| **Live equity** | Measured, not asserted: SOL and USDC in the agent wallet, priced by Jupiter. Phoenix perps collateral and open positions are not counted yet, so the reader under-counts, which errs toward refusing. |
| **UsePod x402 quoting and payment** | Real, on mainnet. `redline/inference.py` quotes the live endpoint and pays in SOL. |
| UsePod completions | Blocked, not by us. A settle request carrying a genuine payment is refused at UsePod's edge with a Cloudflare 403, while forged proofs reach their API normally. Five variables ruled out by direct test, with `cf-ray` ids, in [probe/usepod-x402-settle-block-2026-09-19.md](probe/usepod-x402-settle-block-2026-09-19.md). |
| An in-policy order actually filling at a venue | Not done. `tests/venue_gate.py` proves the refusal against the live venue and gets a real Jupiter quote for the allowed order, then stops before spending. Run it with `--execute` to close it. |
| Phoenix perps | Not available to this account. `perps_account` returns no registered trader, and registration is a private beta the backend controls. The venue path today is spot swaps through Jupiter. |
| Pair-trading strategy (SOL against ETH) | Not built. |
| Referee mode for hosted ClawPump agents | Not claimed, anywhere in this repository. Hosted agents cannot load a plugin. |
| Realised trading performance | Not claimed. No trade has been made. |

## Tech stack

- **Plugin:** Python 3.11+, standard library plus `cryptography` for the signature check · **Tests:** 38 unit + 1 runtime integration + 2 mainnet gates, in CI · **Runtime:** Hermes Agent v2026.9.14+ (`pre_tool_call` hook) · **Site:** Svelte 5 + Vite, static · **Chain:** Solana mainnet, memo program via the `solana` CLI

## Project layout

```
redline/
  __init__.py     # the Hermes hook: pre_tool_call → intent → policy → block or allow → tape
  policy.py       # the rulebook; pure functions plus a small state file; fails closed
  intent.py       # tool call → Intent; anything unpriceable becomes None
  equity.py       # wallet SOL + USDC priced by Jupiter, read from Solana RPC
  tape.py         # hashed records to tape.jsonl; refusals posted as Solana memos
  runtime.py      # wires the live readers in when Hermes loads the plugin
  inference.py    # UsePod x402: quote, pay on Solana, settle (see the honesty table)
  plugin.yaml     # Hermes manifest
tests/            # 20 unit tests + hermes_integration.py (real runtime) + mainnet_gate.py (real chain)
site/             # the tape page (Svelte + Vite)
probe/            # measured facts, dated: Phoenix markets, ClawPump token field, UsePod quote + the settle block
design/logo/      # the mark, wordmark, and the rounds that were rejected
.github/workflows # tests.yml (CI), pages.yml (site)
```

## Run it locally

```bash
python3 -m unittest discover -s tests -t .                       # the rulebook
ln -sfn "$PWD/redline" ~/.hermes/plugins/redline                  # link the plugin into Hermes (v2026.9.14+)
hermes plugins validate ./redline && hermes plugins enable redline
mkdir -p ~/.hermes/redline && echo '{"agent_wallet":"<your ClawPump agent wallet>"}' > ~/.hermes/redline/config.json
cd site && npm install && npm run dev                             # the tape page
```

## Tests

```bash
python3 -m unittest discover -s tests -t .   # → Ran 20 tests ... OK
```

They cover every rule in the policy table, the intent mapping for both ClawPump MCP prefixes, the block return shape, the tape record, and fail-closed behaviour when equity cannot be read. CI runs them on every push: `.github/workflows/tests.yml`.
