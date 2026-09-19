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
import re
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


MAX_SECONDS = 4.6        # longer than this and a caption sits on screen past its welcome
MAX_WORDS = 11
# A caption must not end on a word that is still reaching for the next one. Breaking after "of"
# leaves the reader hanging mid-phrase: "...landing 79 cents of" / "USDC into the agent wallet."
DANGLING = {"of", "the", "a", "an", "and", "to", "in", "on", "at", "for", "with", "from", "that",
            "is", "was", "its", "it", "as", "by", "into", "then", "so", "but", "or", "through"}


def transcribe(audio: Path, out_dir: Path) -> list[dict]:
    """Word-level timings, regrouped into readable lines.

    Whisper's own segments are cut wherever it felt like breathing. On this narration that gave a
    caption reading "...through the real" followed by one starting "Hermes hook, in front of" --
    a sentence torn in half across two cards -- and two cards that sat on screen for eight
    seconds. Regrouping the words fixes both: a line ends at a sentence end, or at a comma when
    it has run long enough, and never runs past MAX_SECONDS.
    """
    subprocess.run(["whisper", str(audio), "--model", "base", "--language", "en",
                    "--word_timestamps", "True", "--output_format", "json",
                    "--output_dir", str(out_dir)], check=True, capture_output=True, text=True)
    data = json.loads((out_dir / (audio.stem + ".json")).read_text())

    words = [w for seg in data["segments"] for w in seg.get("words", [])]
    if not words:
        return data["segments"]          # no word timings: fall back to whisper's own split

    lines, cur = [], []
    for w in words:
        cur.append(w)
        text = "".join(x["word"] for x in cur).strip()
        span = cur[-1]["end"] - cur[0]["start"]
        ends_sentence = text.endswith((".", "!", "?"))
        long_enough = span >= 2.2 or len(cur) >= 7
        last = re.sub(r"[^a-z']", "", cur[-1]["word"].lower())
        dangling = last in DANGLING and not ends_sentence
        hard_limit = span >= MAX_SECONDS + 0.9 or len(cur) >= MAX_WORDS + 3
        if (not dangling and (ends_sentence or (text.endswith(",") and long_enough)
                              or span >= MAX_SECONDS or len(cur) >= MAX_WORDS)) or hard_limit:
            lines.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": text})
            cur = []
    if cur:
        lines.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                      "text": "".join(x["word"] for x in cur).strip()})
    return lines


# Whisper writes names the way it hears them. Correcting the spelling of a word that WAS said is
# right; rewriting a sentence into one that was not said is not, and that line is not crossed here.
NAMES = {
    "Red line": "Redline", "red line": "Redline", "Redline.": "Redline.",
    "Clawpom": "ClawPump", "Clawpum": "ClawPump", "Clawpump": "ClawPump",
    "Claw pump": "ClawPump", "Clawpomp": "ClawPump",
    "Solana Explorer": "Solana explorer", "Salon": "Solana",
    "Hermes pre-tool call": "Hermes pre-tool-call",
    "main net": "mainnet", "Main net": "mainnet", "Mainnet": "mainnet", "test net": "testnet",
    "Test net": "testnet", "mainnet.": "mainnet.",
}


def fix_names(text: str) -> str:
    for wrong, right in NAMES.items():
        text = text.replace(wrong, right)
    # Whisper sometimes starts a segment lowercase where a sentence began. Capitalising the first
    # letter is a formatting fix to a word that was said, not a rewrite of it.
    return text[:1].upper() + text[1:] if text else text


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
