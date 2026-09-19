# Social assets

| File | Size | Use |
|---|---|---|
| `x-header-3000x1000.png` | 3000 x 1000 | upload this one as the X header (X downscales to 1500 wide, stays sharp on retina) |
| `x-header-1500x500.png` | 1500 x 500 | the 1x reference render |
| `x-avatar-400.png` | 400 x 400 | profile picture |
| `x-header-GUIDES.png` | 1500 x 500 | checking only, never upload |
| `header.html` | - | the source; re-render with headless Chrome at `--window-size=1500,500` |

## Safe areas, measured on the live @UseRedline profile (2026-09-19)

- The profile picture covers roughly **x 50-390, y 316-500** of the banner and hangs below it.
  It swallowed the strapline in the first version. All copy now sits above y=300.
- Keep everything inside **x 150-1350** so a side crop on a narrow window cannot clip the
  wordmark or the dial.
- The X phone app enlarges the banner while the timeline is pulled down, which crops both
  sides. That is a transient state, not the resting layout.
