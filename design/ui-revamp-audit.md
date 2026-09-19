# UI revamp — Phase 1 audit

Target: `site/` (four routes). Direction already committed in `design/build-brief.md`; this pass
raises craft, it does not re-decide the world. Bar: `~/.claude/skills/design-taste/examples-landing-brief.md`,
distilled as BB-1..BB-14 in `build-brief-method.md`.

Corpus read: craft-floor.md, build-brief-method.md, style.config.md, copy-rules.md.

## 0. What the automated audit says, and why that is not the finding

`node ~/.claude/skills/ui-revamp/scripts/audit.js site/src` → no violations. The five-minute
detector also passes: no linear easing, no `scale(0)`, no `transition: all`, radius comes from
tokens, inputs are 16px. That proves nothing is broken. It does not reach the question this pass
is about, which is whether the page reproduces a composition or assembles one.

## 1. A functional defect, found by looking rather than by grepping

**Severity: critical. The live site was rendering the tape and the policy as empty headings.**

`Cannot read properties of undefined (reading 'market')`. The tape grew two record shapes that
carry no order, an operator action and an internal error, and the page read straight through
`record.intent.market`. A throw inside a Svelte each-block takes the rest of the block with it, so
24 records and 13 policy rows vanished while the status line above them still said "24 orders
judged". Neither the build, nor 101 Python tests, nor the craft audit could see it, because none
of them render a page.

Fixed, and the record-to-words logic now lives in `site/src/lib/record.js` with ten tests in
`tape.test.js` that feed it the real tape plus shapes that do not exist yet. Added to CI.

## 2. Craft gaps against BB-1..BB-14

| # | Gap | Evidence |
|---|---|---|
| BB-2 | No artboard unit system. Every length is a raw px literal. | 26×`13px`, 24×`1px`, 21×`14px`, 19×`3px`, 15×`20px` in component CSS |
| BB-3 | No nested component unit. Card insides re-layout at different widths. | `container-type` appears 0 times across all four routes |
| BB-4 | No hairline floor. | 24 raw `1px` borders, none `max(1px, …)` |
| BB-5 | No gradient rims. Elevated surfaces are a border plus one shadow step. | no `mask-composite` anywhere |
| BB-8 | No transition spine. Nothing carries a state change. | the dial, the declared signature element, is drawn at a fixed angle and never moves |
| BB-10/11 | No load reveal at all, so no timing table and no reveal-to-`var(--o)`. | the page appears at once; the live equity arrives ~2s later and pops in with no ceremony |
| BB-13 | Reduced motion is declared but has nothing to reduce. | `app.css` has the media query; no entrance exists |

## 3. Craft floor

- **CF-4 violation, whole route.** `Guide.svelte` has 2 interactive elements and 0 `:focus-visible`
  rules. The other three routes are covered.
- **CF-6 partial.** The type scale is ad-hoc per element, not tokens: 13px used 26 times, 14px 21
  times, 15px 10 times. Three `clamp()` display sizes exist, which is the good part.
- CF-1, CF-2, CF-3, CF-5, CF-7: pass.

## 4. Visual evaluation

**Blur test at 7px, first viewport: passes.** The headline reads first, the dial second, the red
arc and needle hold their shape, the two figures read as a pair. I expected the dark install block
to dominate and it does not, because it is below the fold. Recording that because the expectation
was wrong and the test is the reason I know.

What the blur does expose:
- The hero's left column is an undifferentiated grey mass. Six lines of 15px monospace at a wide
  measure have no silhouette.
- Section rhythm is uniform. Every gap is the same, against style.config's "varied section
  treatments, never uniform".
- Roughly 120px of dead band at the top of the viewport and 50px at the bottom.

## 5. Not a finding

The five borrowed corporate logos and the three invented metrics in the reference brief are not
portable. `build-brief-method.md` says so in its own cautions, and `copy-rules.md` rule 3 bans
invented realism outright. Redline's equivalent of a trust strip is the on-chain receipts, which
are real and already on the page. Nothing here adopts that part of the reference.
