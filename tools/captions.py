"""Caption the cut from the audio, not from the script.

Whisper reads the voice takes and reports when each sentence was actually said. Those times are
shifted by where the take sits in the cut, from demo/timeline.json, and written as an SRT.

The result is a first draft, not a finished caption track. Whisper spells names the way it hears
them, so read every line against what you said before shipping. Fixing the spelling of a word you
did say is right. Rewriting a sentence into one you did not say is not: then the captions and the
audio disagree and anyone reading along catches it.

  python3 tools/captions.py
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

DEMO = Path("demo")
SRT = DEMO / "captions.srt"


def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe(audio: Path, out_dir: Path) -> list[dict]:
    subprocess.run(["whisper", str(audio), "--model", "base", "--language", "en",
                    "--output_format", "json", "--output_dir", str(out_dir)],
                   check=True, capture_output=True, text=True)
    return json.loads((out_dir / (audio.stem + ".json")).read_text())["segments"]


# Whisper writes names the way it hears them. Correcting the spelling of a word that WAS said is
# right; rewriting a sentence into one that was not said is not, and that line is not crossed here.
NAMES = {
    "Red line": "Redline", "red line": "Redline", "Redline.": "Redline.",
    "Clawpom": "ClawPump", "Clawpum": "ClawPump", "Clawpump": "ClawPump",
    "Claw pump": "ClawPump", "Clawpomp": "ClawPump",
    "Solana Explorer": "Solana explorer", "Salon": "Solana",
    "Hermes pre-tool call": "Hermes pre-tool-call",
}


def fix_names(text: str) -> str:
    for wrong, right in NAMES.items():
        text = text.replace(wrong, right)
    return text


def main() -> int:
    timeline = json.loads((DEMO / "timeline.json").read_text())
    lines, n = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for take in timeline["voice"]:
            audio, at = Path(take["file"]), take["at"]
            for seg in transcribe(audio, Path(tmp)):
                text = fix_names(seg["text"].strip())
                if not text:
                    continue
                n += 1
                lines.append(f"{n}\n{stamp(at + seg['start'])} --> {stamp(at + seg['end'])}\n{text}\n")
                print(f"  {stamp(at + seg['start'])}  {text}")
    SRT.write_text("\n".join(lines))
    print(f"\n  {n} captions -> {SRT}")
    print("  Read every line above against what you actually said before building the final cut.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
