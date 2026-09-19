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
- [ ] Foundation: artboard unit `--u`, `--hairline`, tokenized type scale
- [ ] The dial becomes the transition spine: the needle sweeps when real equity lands
- [ ] Load reveal with a timing table in ms, reveal to `var(--o)`
- [ ] Nested unit `--cu` on the dial card and the tape row
- [ ] Craft floor: `:focus-visible` on the guide route, gradient rims on elevated surfaces
- [ ] Rhythm: vary the section spine, give the hero column a measure and a shape
- [ ] Write every value into `design/build-brief.md` with an acceptance checklist

## Phase 4: Validate
- [ ] Automated audit passes
- [ ] Blur test and squint test on all four routes
- [ ] Reduced motion is a real branch, checked by rendering with it on
- [ ] 390px: no horizontal overflow on any route
- [ ] Before/after → `design/ui-revamp-before-after.md`
