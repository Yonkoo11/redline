"""Burn the caption track into the cut.

The ffmpeg on this machine is built without libass, so it has neither the `subtitles` filter nor
`drawtext`. Rather than swap the whole toolchain out, each caption is drawn to a transparent PNG
here and overlaid for its own span. Same result, and the type is under our control instead of
libass's defaults.

  python3 tools/burn-captions.py            # demo/redline.mp4 + demo/captions.srt -> demo/redline-captioned.mp4
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEMO = Path("demo")
SRC, SRT = DEMO / "redline.mp4", DEMO / "captions.srt"
OUT = DEMO / "redline-captioned.mp4"
CARDS = DEMO / "work" / "captions"

W, H = 1920, 1080
SIZE, MARGIN, PAD, LINE = 40, 72, 22, 54
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
MAX_CHARS = 62


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    def secs(t: str) -> float:
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    out = []
    for block in path.read_text().strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"(.+?) --> (.+)", lines[1])
        if m:
            out.append((secs(m.group(1)), secs(m.group(2)), " ".join(lines[2:])))
    return out


def wrap(text: str) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > MAX_CHARS and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:3]


def card(text: str, path: Path) -> None:
    font = ImageFont.truetype(FONT, SIZE)
    lines = wrap(text)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    widths = [d.textlength(l, font=font) for l in lines]
    box_w = max(widths) + PAD * 2
    box_h = LINE * len(lines) + PAD * 2 - 10
    x0, y0 = (W - box_w) / 2, H - MARGIN - box_h
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=10, fill=(12, 12, 14, 214))
    for i, line in enumerate(lines):
        d.text(((W - widths[i]) / 2, y0 + PAD - 6 + i * LINE), line, font=font, fill=(245, 244, 240, 255))
    img.save(path)


def main() -> int:
    if not SRC.exists() or not SRT.exists():
        raise SystemExit("need demo/redline.mp4 and demo/captions.srt; run build-video.py then captions.py")
    caps = parse_srt(SRT)
    if not caps:
        raise SystemExit(f"no captions parsed out of {SRT}")
    CARDS.mkdir(parents=True, exist_ok=True)

    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(SRC)]
    for i, (_, _, text) in enumerate(caps):
        p = CARDS / f"{i:03d}.png"
        card(text, p)
        args += ["-i", str(p)]

    chain, prev = [], "0:v"
    for i, (start, end, _) in enumerate(caps):
        label = f"v{i}"
        chain.append(f"[{prev}][{i + 1}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{label}]")
        prev = label
    args += ["-filter_complex", ";".join(chain), "-map", f"[{prev}]", "-map", "0:a?",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", str(OUT)]

    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(p.stderr[-1000:])
    print(f"  {len(caps)} captions burned -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
