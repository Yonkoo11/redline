# UI revamp progress

## Phase 1: Audit
- [x] Run automated audit script (`site/src`, no violations) and the five-minute detector
- [x] Heuristic evaluation, including the blur test on the first viewport
- [x] Visual inventory: radius (tokens, clean), spacing, 8 distinct font sizes, px literal counts
- [x] Document findings → `design/ui-revamp-audit.md`
- [x] Fix the critical defect found while looking: the tape and policy rendered empty on the live
      site because a record with no order threw inside the each-block

## Phase 2: Plan
- [x] Findings summarised, ordered by what a first-time viewer sees first
- [x] Implementation order below
- [x] Proceeding: the standing instruction is to handle it, and every step is reversible and
      published behind CI

## Phase 3: Implement
- [x] Foundation: artboard unit `--u`, `--hairline`, tokenized type scale (`site/src/app.css`)
- [x] The dial becomes the transition spine: the needle sweeps when real equity lands
      (`.needle`, 1400ms, `cubic-bezier(.16,1,.3,1)`), and a `settled` hold of 1180ms so the
      sweep is never missed
- [x] Load reveal with a timing table in ms, reveal to `var(--o)` (`design/build-brief.md` §12)
- [x] Nested unit `--cu` on the dial card (`.housing`, `container-type:inline-size`), with its
      internal breakpoints as `@container` rather than `@media`
- [~] The tape row was left on viewport media queries. It is always laid out at the full page
      measure and never nested in a narrower context, so a container adds a mechanism with
      nothing behind it. Recorded rather than done.
- [x] Craft floor: `:focus-visible` on every interactive element including the guide route,
      mask-composite gradient rim on the elevated dial card
- [x] Rhythm: the hero column carries a measure, the install slab breaks the light field
- [x] Write every value into `design/build-brief.md` with an acceptance checklist (§13)

## Phase 4: Validate
- [x] Automated audit passes (`audit.js site/src` → no violations)
- [x] Blur test and squint test on all four routes, desktop and phone, by rendering and looking
- [x] Reduced motion is a real branch, checked by rendering with it on: 0 of 5 revealed elements
      left invisible
- [x] 390px: no horizontal overflow on any of the four routes (was failing on `/policy/` by 10px)
- [x] Before/after → `design/ui-revamp-before-after.md`
