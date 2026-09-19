# Build brief — Redline tape page

Every number here is a decision, not a suggestion. Where a value is given, use it exactly. Where
copy is given, use it verbatim. Read the whole brief before writing a line.

**Output contract:** three files only — `site/src/App.svelte`, `site/src/app.css`,
`site/index.html`. Svelte 5 runes, Vite, no framework additions, no CSS library, no icon package,
no component library. Do not add routes, a nav, a footer link farm, or any section not listed here.

**Direction:** hybrid of proposal 1 (world, type, dial) and proposal 3 (first-viewport rule), with
one sentence carried from proposal 2. Decided in `ai/design-progress.md` phase_3.

---

## 1. World and tokens

Light. This is decided on evidence and recorded in phase_3; do not "improve" it to dark.

```css
--paper:#F4F3EF; --paper-2:#EDEBE5; --paper-3:#E5E2DA;
--ink:#131417; --ink-2:#4A4C52; --ink-3:#8B8D93;
--red:#E03A2F;
--rule:rgba(19,20,23,.14); --rule-soft:rgba(19,20,23,.07);
--r-sm:3px; --r-md:6px; --r-lg:10px; --r-full:999px;
--e-1:0 1px 2px rgba(19,20,23,.05);
--e-2:0 1px 2px rgba(19,20,23,.05), 0 6px 14px -8px rgba(19,20,23,.22);
--e-3:0 1px 2px rgba(19,20,23,.05), 0 14px 32px -14px rgba(19,20,23,.30);
--ease:cubic-bezier(.22,1,.36,1); --t-fast:140ms; --t:220ms;
--s1:4px; --s2:8px; --s3:12px; --s4:16px; --s6:24px; --s8:32px; --s12:48px; --s16:64px; --s24:96px;
```

**Shadow philosophy (CF-5): soft-elevation ladder.** Light world, so elevation is the `--e-1/2/3`
ladder plus a background delta from `--paper` to `--paper-2`. No pixel-offset shadows, no glow
except the one pulse named in §6. Never a lone `0 4px 20px rgba(0,0,0,.1)`.

**Ground texture:** two layers on `body`, both required.
```css
background-image:
  linear-gradient(var(--rule-soft) 1px, transparent 1px),
  radial-gradient(120% 70% at 78% 0%, rgba(224,58,47,.055), transparent 62%);
background-size: 100% 28px, 100% 100%;
```
The 28px rule grid is instrument-dial printing. The red wash is the only gradient on the page and
sits at .055, above the .08 floor only because it is a ground wash and not an accent glow; the
accent glow that must clear .08 is the state dot in §6.

**Radius by role, never ad hoc:** controls `--r-sm`, panels `--r-lg`, the dial housing `--r-lg`,
the state dot `--r-full`. Zero literal `border-radius` values in component CSS.

## 2. Type

| Role | Face | Size | Weight | Line height | Tracking |
|---|---|---|---|---|---|
| h1 | Barlow Condensed | `clamp(46px,7.4vw,84px)` | 800 | .92 | -.022em |
| h2 section | Barlow Condensed | `clamp(26px,3vw,36px)` | 800 | 1 | -.01em |
| h3 install | Barlow Condensed | `clamp(22px,2.6vw,30px)` | 800 | 1.05 | -.01em |
| brandword | Barlow Condensed | 30px | 800 | 1 | .01em |
| body / sub | IBM Plex Mono | 16px | 400 | 1.5 | 0 |
| record reason | IBM Plex Mono | 14px | 400 | 1.45 | 0 |
| readout value | IBM Plex Mono | 28px | 600 | 1.1 | 0, `tabular-nums` |
| labels, verdicts | IBM Plex Mono | 12px | 600 | 1 | .14em, uppercase |
| meta | IBM Plex Mono | 12px | 400 | 1.4 | 0 |

Ratio h1:body is 84:16 = 5.25x at the top of the clamp (SR-2 wants ≥3x). Two faces, each with an
assigned job (SR-4): Barlow Condensed is display only and never sets a sentence; IBM Plex Mono sets
everything a person reads and every number. `-webkit-font-smoothing:antialiased` globally.
`font-variant-numeric:tabular-nums` on every number.

Fonts load from Google with `preconnect`; weights 500/600/800 for Barlow Condensed, 400/500/600 for
IBM Plex Mono. No other weights.

## 3. Structure, in order. No other sections.

1. **Masthead** — mark 30px, wordmark, right-aligned `SOLANA MAINNET` label, 2px solid ink bottom rule.
2. **State line** — pulsing dot + one sentence, 1px rule under.
3. **First viewport block** — a two-column grid at ≥900px, `minmax(0,44%) minmax(0,1fr)`, gap `--s16`.
   Left: h1, sub, claim. Right: the dial housing, and **directly beneath it inside the same housing,
   the single most recent refusal with its receipt link.** This is the whole point of the hybrid: the
   proof is on screen before any scroll. Below 900px it stacks, dial first after the copy.
4. **The tape** — section head, then every record as a hairline row.
5. **The policy** — section head, then nine limits in a two-column list at ≥700px.
6. **Install** — ink-on-paper inverted block, one command, one copy button.
7. **Footer** — three links, 2px solid ink top rule.

## 4. The dial (signature element, first viewport)

SVG, `viewBox="0 0 520 300"`, width 100%.

- Face: `path M 40 270 A 220 220 0 0 1 480 270`, filled with a vertical gradient `#F7F6F2 → #E4E1D9`,
  stroked `rgba(19,20,23,.16)` at 2px.
- Ticks: 9 marks, stroke `rgba(19,20,23,.45)` at 2px, coordinates as in `proposals/proposal-1.html`.
- Red band: `path M 372 96 A 220 220 0 0 1 480 270`, stroke `--red`, width 16, `stroke-linecap:butt`.
  The word `CAP` in IBM Plex Mono 13/600, `--red`, rotated 52°, at (418,140).
- Needle: a `<g>` carrying **only** the SVG attribute `transform="rotate(DEG 260 270)"`. **Do not set
  `transform-box` or `transform-origin` in CSS on this group** — in proposal 1 that combination moved
  the needle off the canvas and it did not draw. Transition `transform 900ms var(--ease)`.
  Needle body `M252 258 L268 258 L263 96 L257 96 Z` fill `--ink`; hub `circle r=17` fill `--ink`;
  hub centre `circle r=5` fill `#E4E1D9`.
- Rest angle `-42`. On a successful read, animate to the angle for the last judged order:
  `clamp(-42, -42 + 106 * (notional / cap) / 9, 64)`; with the real record (15.32 against 1.70) this
  lands at 64, hard against the red band. If the read fails the needle stays at rest.

## 5. Copy — verbatim

- Masthead right label: `SOLANA MAINNET`
- State line: **`Holding.`** then ` 2 orders judged, 1 refused, and the refusal is on chain.`
  The count is generated from the tape, not typed: `{n} orders judged, {r} refused`.
- h1: `Kill switch for ` + `claw traders` in `--red` + `.`
- Sub, one paragraph: `An agent may trade as hard as it likes, right up to the line. It cannot cross
  it. Redline sits between the model and the wallet: every order passes the policy its operator
  signed, or it is refused and the refusal is written to Solana.`
- Claim block, `border-left:3px solid var(--red)`, padding-left `--s4`:
  bold lead `111 of the 200 newest tokens on ClawPump describe a trading agent.` then
  ` The platform gives them a daily model-spend budget and an address whitelist. No per-order cap. No
  daily loss limit. No drawdown halt.` then a `<cite>`: `Measured from clawpump.tech, 18 September 2026`
- Dial readout labels: `AGENT EQUITY, LIVE` and `CAP PER ORDER`
- Under equity: `FT5GaRv2…jSZirz, read from Solana in your browser`
- Under cap: `10% of equity, from the signed policy`
- Section heads: `The tape` / label `every order judged, newest first`; `The policy` / label
  `signed by the operator, enforced on every call`
- Install h3: `Put it in front of your agent`
- Install p: `Redline is a Hermes plugin. It never holds a key, it refuses when it cannot read the
  balance, and it is MIT licensed.`
- Command: `hermes plugins install Yonkoo11/redline && hermes plugins enable redline`
- Allowed rows carry, on the right: `no receipt — only refusals are written`
- Footer: `Source` → the repo · `@useredline` → x.com/useredline · `The AnsemHack Clawrena`

No headline, tagline or claim beyond this list. Nothing here is a model-written adjective.

## 6. Live data

- **Balance:** `POST https://solana-rpc.publicnode.com`, `getBalance`, param the agent wallet.
  **Not `api.mainnet-beta.solana.com`** — measured 2026-09-19, it refuses browser requests and the
  page shows "unavailable". This is the one deviation from proposal 1 and this is why.
- **Price:** `GET https://lite-api.jup.ag/price/v3?ids=So111…112`, read `.usdPrice`.
- Equity = lamports/1e9 × price. Cap = equity × 0.10.
- **State dot:** `--red`, 8px, `--r-full`, pulse keyframe from `box-shadow 0 0 0 0 rgba(224,58,47,.45)`
  to `0 0 0 9px rgba(224,58,47,0)` over 2.4s. This is the page's one element that moves without
  interaction, and its glow starts at .45, clearing the .08 floor.
- Failure copy, exactly: equity reads `unavailable`, and the note under it becomes
  `Solana RPC or the price feed did not answer. The tape below is unaffected.` The tape still renders.
- Loading: equity reads `reading…`, cap reads `—`, needle at rest.

## 7. Interactive states (CF-4)

Every interactive element gets hover **and** `:focus-visible`, hover inside `@media (hover:hover)`.

- Receipt links: `border-bottom:1px solid var(--red)`, hover changes colour to `--red`;
  focus-visible `box-shadow:0 0 0 3px rgba(224,58,47,.35)`.
- Copy button: min-height 44px, hover `translateY(-1px)` + `0 6px 16px -6px rgba(224,58,47,.8)`,
  active `scale(.97)` at 80ms, focus-visible `0 0 0 3px rgba(224,58,47,.45)`.
  On click it writes the command to the clipboard, swaps its label to `Copied` for 1600ms.
- Refused rows: `box-shadow: inset 3px 0 0 var(--red)` plus
  `background: linear-gradient(90deg, rgba(224,58,47,.055), transparent 56%)`. Allowed rows plain.
  This is Cloudflare's tint-and-rule, not a second card style.
- `prefers-reduced-motion`: all durations to 1ms, pulse off.

## 8. Deviations from the chosen direction, named

1. The RPC host changes, for the measured reason in §6.
2. The dial housing now also holds the most recent refusal, taken from direction 3, so the first
   viewport carries proof. Direction 1 put the tape below the fold.
3. The sub is direction 2's sentence, because it states the mechanism better than direction 1's did.
4. The needle no longer carries CSS `transform-box`/`transform-origin`, which is what broke it.

## 9. Acceptance checklist — each line independently checkable

- [ ] Exactly three files changed: `site/src/App.svelte`, `site/src/app.css`, `site/index.html`.
- [ ] `grep -c "border-radius:" site/src/App.svelte` returns 0 outside `:root`; all radii are tokens.
- [ ] Every surface with elevation uses `--e-1/2/3` plus a paper-step background; no `border`-only card.
- [ ] `:focus-visible` appears at least twice; every `:hover` block changes transform or box-shadow, never colour alone.
- [ ] At least one `clamp()` on display type.
- [ ] `tabular-nums` present on the readout and every record number.
- [ ] No `transition: all`, no `#000000`, no `#ffffff`, no hardcoded hex outside `:root`.
- [ ] Page reads the balance from `solana-rpc.publicnode.com` and the price from Jupiter, in the browser.
- [ ] Needle is visible on screen at rest and after a successful read.
- [ ] The most recent refusal and its Solscan link are on screen at 1280×900 without scrolling.
- [ ] Desktop 1280 and phone 390 screenshots taken, looked at, no overflow, no orphan, no dead flat band.
- [ ] Not one word of copy, one colour or one URL differs from this brief.
