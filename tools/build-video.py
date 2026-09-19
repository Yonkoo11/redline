"""Cut the demo video from the shots on disk.

The voice sets the length of every shot. A clip shorter than the line spoken over it holds its
last frame; a clip longer than the line is trimmed. The one exception is the core action, which is
marked `fixed` in the edit list: it runs its own length and the voice has to fit inside it,
because the waiting in it is the evidence.

  python3 tools/build-video.py            # build from demo/edit.json
  python3 tools/build-video.py --check    # report what it would do, touch nothing
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEMO = Path("demo")
WORK = DEMO / "work"
OUT = DEMO / "redline.mp4"
W, H, FPS = 1920, 1080, 30


def run(args: list[str]) -> str:
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"failed: {' '.join(args[:4])}...\n{p.stderr[-800:]}")
    return p.stdout


def duration(path: Path) -> float:
    """How long a clip runs, whatever the container admits to.

    Chrome writes webm without a duration in the container, so `format=duration` comes back as
    N/A and float() throws. The stream usually knows; when it does not, decoding the file and
    reading the last timestamp always does, and seven short clips are cheap to decode.
    """
    for entries in ("format=duration", "stream=duration"):
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
                   "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).strip().split("\n")[0]
        try:
            value = float(out)
            if value > 0:
                return value
        except ValueError:
            pass
    p = subprocess.run(["ffmpeg", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True)
    stamps = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not stamps:
        raise SystemExit(f"cannot determine the length of {path}")
    h, m, sec = stamps[-1]
    return int(h) * 3600 + int(m) * 60 + float(sec)


def render_cast(cast: Path) -> Path:
    """An asciicast becomes video via agg. --idle-time-limit keeps the waits: agg caps them at
    five seconds by default, which silently cut three seconds out of a take."""
    gif, mp4 = WORK / (cast.stem + ".gif"), WORK / (cast.stem + ".cast.mp4")
    run(["agg", "--font-size", "28", "--idle-time-limit", "60", str(cast), str(gif)])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gif), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
         f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x121212",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(mp4)])
    return mp4


def fit(src: Path, target: float, out: Path) -> None:
    """Make src exactly `target` seconds: trim if long, hold the last frame if short."""
    have = duration(src)
    pad = f",tpad=stop_mode=clone:stop_duration={target - have + 0.5:.3f}" if have < target else ""
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an", "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
         f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x121212,fps={FPS}{pad}",
         "-t", f"{target:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)])


def main() -> int:
    check = "--check" in sys.argv
    for tool in ("ffmpeg", "ffprobe", "agg"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is not installed")
    edit = json.loads((DEMO / "edit.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)

    parts, audio_bits, t = [], [], 0.0
    for i, shot in enumerate(edit["shots"]):
        src = Path(shot["clip"])
        if not src.exists():
            raise SystemExit(f"missing clip: {src}")
        cast_len = None
        if src.suffix == ".cast":
            # In check mode the cast is not rendered, so read its own last event time instead of
            # reporting a length that is not the take's.
            events = [json.loads(l) for l in src.read_text().splitlines() if l.startswith("[")]
            cast_len = round(events[-1][0], 2) + 3.0 if events else 0.0
            if not check:
                src = render_cast(src)
        voice = Path(shot["voice"]) if shot.get("voice") else None
        if voice and not voice.exists():
            print(f"  {shot['id']}: no voice yet at {voice}, silence for now")
            voice = None
        spoken = duration(voice) if voice else 0.0
        if shot.get("fixed"):
            target = cast_len if check else duration(src)
        else:
            target = max(spoken + shot.get("pad", 0.8), shot.get("min", 3.0))
        if shot.get("fixed") and spoken > target:
            print(f"  ! {shot['id']}: the voice runs {spoken - target:.1f}s longer than the take. "
                  f"Cut words, not the take.")
        print(f"  {shot['id']:<16} clip {src.name:<22} voice {spoken:5.2f}s -> {target:5.2f}s"
              + ("  (fixed: the take sets the length)" if shot.get("fixed") else ""))
        if not check:
            part = WORK / f"{i:02d}-{shot['id']}.mp4"
            fit(src, target, part)
            parts.append(part)
            if voice:
                audio_bits.append((t, voice))
        t += target

    print(f"  total {t:.1f}s")
    # Where every voice take starts in the finished cut. tools/captions.py reads this so the
    # caption timings come from one place rather than being worked out twice.
    (DEMO / "timeline.json").write_text(json.dumps(
        {"total": round(t, 3),
         "voice": [{"at": round(off, 3), "file": str(v)} for off, v in audio_bits]}, indent=1) + "\n")
    if check:
        return 0

    listing = WORK / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    silent = WORK / "silent.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(silent)])

    if audio_bits:
        args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
        for _, v in audio_bits:
            args += ["-i", str(v)]
        delays = "".join(
            f"[{n + 1}:a]adelay={int(off * 1000)}|{int(off * 1000)}[a{n}];"
            for n, (off, _) in enumerate(audio_bits))
        mix = "".join(f"[a{n}]" for n in range(len(audio_bits)))
        args += ["-filter_complex",
                 f"{delays}{mix}amix=inputs={len(audio_bits)}:normalize=0:dropout_transition=0,"
                 f"apad[out]",
                 "-map", "0:v", "-map", "[out]", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-t", f"{t:.3f}", str(OUT)]
        # Not -shortest. The last shot holds after the last word, and -shortest cut that hold off.
        run(args)
    else:
        shutil.copy(silent, OUT)

    srt = DEMO / "captions.srt"
    if srt.exists():
        burned = DEMO / "redline-captioned.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT), "-vf",
             f"subtitles={srt}:force_style='FontName=Helvetica,FontSize=22,"
             f"PrimaryColour=&HFFFFFF&,BorderStyle=3,Outline=1,Shadow=0,MarginV=60'",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(burned)])
        print(f"  captioned: {burned}")
    print(f"  {OUT}  {duration(OUT):.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
