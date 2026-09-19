# Redline site — what the revamp changed

Four routes: `/`, `/policy/`, `/log/`, `/guide/`. One committed direction (paper `#F4F3EF`,
ink `#131417`, one red `#E03A2F`, ruled field, the dial as the signature element). No new
direction was invented here; this pass raised the craft against `design/build-brief.md`.

Every line below was checked by rendering the page and looking at it, at 390 / 760 / 980 /
1180 / 1440, in both motion branches, against a local `vite preview`.

## The defect that mattered most

**Before:** the tape and the policy rendered as two empty headings on the live site. A record
with no `intent` (an operator action, an internal error) reached `record.intent.market`, threw,
and a throw inside a Svelte each-block takes the whole list with it. Nothing in the build or the
test suite could see it, because neither renders a page.

**After:** the record-to-words logic lives in `site/src/lib/record.js`, every function tolerates
a shape it has never seen, and `site/src/lib/tape.test.js` feeds it the real tape plus the
shapes a future version might write. 10 tests, wired into CI.

## Craft

| | Before | After |
|---|---|---|
| Sizing | px literals scattered across four components | one artboard unit `--u` (1440 reference, capped at 1.08px) and `--hairline`, both tokenized |
| Type | 8 ad-hoc sizes | a named scale: display / h2 / h3 / lede / body / meta / fine / label |
| The dial | static; the needle appeared at its final angle | the needle sweeps 1400ms on `cubic-bezier(.16,1,.3,1)` when real equity lands, and the settled state is held 1180ms so the sweep is never missed |
| The dial card | `@media` breakpoints, so it answered to the window | `container-type:inline-size` with `--cu`; it answers to its own width — 342px → 1 column, 570px → 2, 712px → 3 |
| Load | everything arrived at once | a reveal with a written timing table in ms (state line 130/520, headline 250/520, dial 300/720, sub 430/560, claim 580/560), revealing to `var(--o)` so a dimmed element stays dimmed |
| Reduced motion | the browser default branch was never rendered or checked | a real branch, verified by emulating it: 0 of 5 revealed elements are left invisible |
| Elevation | flat surfaces | mask-composite gradient rim on the elevated card |
| Focus | missing on the guide route | `:focus-visible` on every interactive element on all four routes |

## Two things a reader would have felt

**The home tape was the whole log.** All 24 verdicts, and `/log/` — the full reader, with its own
filters — sat behind a nav link repeating the same rows. The home page now carries the 8 newest
and ends with a line out to the full 24. The evidence still leads; the page stopped restating it.

**One sentence appeared twelve times.** Every allowed row carried "no receipt, only refusals are
written" in its right column. It is a rule about the tape, not a fact about a row, so it is said
once now, in the section head: "newest first. only refusals get a receipt."

## The one failure the acceptance run caught

`/policy/` overflowed horizontally by 10px at 390. Cause: at the single-column breakpoint the
builder's grid was `1fr`, whose automatic minimum is the content's min-content width, and the
fixed 190px number input could not shrink under it. Fixed with `minmax(0,1fr)` and a shrinkable
input. The JSON preview still scrolls inside its own frame, which is what it is for.

## Acceptance, as run

```
reduced-motion: {"hiddenAfterLoad":0,"total":5}
problems: none
```

Four routes × five widths × both motion branches. The craft audit reports no violations.

## Not done, and why

- The tape row was left on viewport media queries rather than given a container unit. It is
  always laid out at the full page measure and is never nested in a narrower context, so a
  container would be a mechanism with nothing behind it.
