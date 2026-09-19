"""Generate the narration with Gemini TTS.

Used only because the operator explicitly chose a synthetic voice after being told twice what it
costs: the pipeline's default voice is recognisable, and a judge who has watched ten hackathon
videos that day has heard it before. The honest alternative is a human take; see DECISIONS.md.

The narration is generated in ONE call, not shot by shot, so the prosody is consistent across the
video, then split at the silences between segments. Splitting is verified: if the split does not
produce exactly one chunk per shot, nothing is written and the run fails loudly rather than
quietly mapping the wrong audio to the wrong picture.

  python3 tools/tts.py            # -> demo/vo-1.m4a ... demo/vo-6.m4a
"""
from __future__ import annotations

import base64
import json
import os
import re
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

DEMO = Path("demo")
# Tried in order. The pro model is the best of the three and also the first to answer 429, so
# the flash models stand behind it rather than the run just failing.
MODELS = ["gemini-2.5-pro-preview-tts", "gemini-3.1-flash-tts-preview",
          "gemini-2.5-flash-preview-tts"]
# Asking for the pause explicitly, because the length of an unprompted one varies run to run and
# a run where the segment breaks are no longer than the sentence pauses cannot be split at all.
STYLE = ("Read this narration in a calm, measured, matter-of-fact tone, like someone explaining "
         "their own work to one person. Wherever a line reads [BREAK], pause for two full "
         "seconds and do not say the word.\n\n")
# One segment per call now, so the pause instruction is vestigial but harmless in the prompt.
# Kept for the record: the one-call-plus-split approach this replaced.
GAP_SENTENCE = "\n[BREAK]\n"
SILENCE_DB = "-35dB"
MIN_SILENCE = 0.35        # catch every pause; the segment breaks are picked out by rank below
SEPARATION = 1.15         # a segment break must be this much longer than the longest sentence pause


def synth(text: str, voice: str) -> tuple[bytes, str]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set")
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    last = ""
    for model in MODELS:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"x-goog-api-key": key, "Content-Type": "application/json",
                     "User-Agent": "redline/0.2"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            last = f"{model}: HTTP {e.code}"
            print(f"  {last}, trying the next model")
            continue
        part = d["candidates"][0]["content"]["parts"][0]
        return base64.b64decode(part["inlineData"]["data"]), model
    raise SystemExit(f"no speech model answered ({last})")


def wav(pcm: bytes, path: Path, rate: int = 24000) -> None:
    """Gemini returns raw signed 16-bit mono PCM. Give it a header so ffmpeg will read it."""
    head = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH",
            16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm)))
    path.write_bytes(head + pcm)


def silences(path: Path) -> list[tuple[float, float]]:
    p = subprocess.run(["ffmpeg", "-i", str(path), "-af",
                        f"silencedetect=noise={SILENCE_DB}:d={MIN_SILENCE}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(starts, ends))


def main() -> int:
    """One call per segment.

    The skill says to generate the whole narration in one call and slice it at the silences, for
    consistent prosody. That was tried three times. Each run put the pauses in different places
    and ranked them differently, and on the third the slices carried the wrong lines entirely:
    segment 4a came back reading segment 3's closing sentence. The transcript check caught it
    every time and threw the audio away, which is the check working and the method failing.

    So: one call per segment, same style prompt each time, and every piece transcribed and
    matched against the line it is supposed to carry before anything is kept. Prosody drifts a
    little between segments. Wrong words over the wrong picture is worse.
    """
    spec = json.loads((DEMO / "narration.json").read_text())
    ids = list(spec["lines"].keys())
    (DEMO / "work").mkdir(parents=True, exist_ok=True)

    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        ids = [i for i in ids if i in only]
        print(f"  regenerating only: {', '.join(ids)}")

    made = []
    for seg in ids:
        line = spec["lines"][seg]
        pcm, used = synth(STYLE + line, spec["voice"])
        raw = DEMO / "work" / f"vo-{seg}.wav"
        wav(pcm, raw)
        out = DEMO / f"vo-{seg}.m4a"
        # atempo 1.12 is the skill's tightening step for TTS. Nothing else speeds this audio up:
        # the cut runs at 1.0, so the two mechanisms cannot stack.
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                        "-af", "atempo=1.12", "-ar", "44100", "-c:a", "aac", "-b:a", "192k",
                        str(out)], check=True)
        made.append(out)
        print(f"  vo-{seg}.m4a  {length(out):5.2f}s  ({used.split('-')[1]})")

    print("\n  checking each piece against the line it should carry:")
    bad = []
    for seg in ids:
        heard = transcribe(DEMO / f"vo-{seg}.m4a")
        score = overlap(heard, spec["lines"][seg])
        print(f"    vo-{seg}: {'ok   ' if score >= 0.6 else 'WRONG'} {score:.0%} — "
              f"{heard[:56].replace(chr(10), ' ')}")
        if score < 0.6:
            bad.append(seg)
    if bad:
        for f in made:
            f.unlink(missing_ok=True)
        raise SystemExit(f"these pieces do not carry their line: {bad}. All audio removed.")
    print("\n  every piece carries its line.")
    return 0


def length(path: Path) -> float:
    """Duration, however the container answers. aac in mp4 sometimes reports N/A."""
    for entries in ("format=duration", "stream=duration"):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of",
                              "default=noprint_wrappers=1:nokey=1", str(path)],
                             capture_output=True, text=True).stdout.strip().split("\n")[0]
        try:
            v = float(out)
            if v > 0:
                return v
        except ValueError:
            pass
    return 0.0


def transcribe(path: Path) -> str:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["whisper", str(path), "--model", "base", "--language", "en",
                        "--output_format", "txt", "--output_dir", tmp],
                       check=True, capture_output=True, text=True)
        return (Path(tmp) / (path.stem + ".txt")).read_text().strip()


def overlap(heard: str, wanted: str) -> float:
    """Share of the intended words that were actually said. Whisper spells names its own way, so
    this is deliberately a word-overlap score and not an exact match."""
    norm = lambda t: set(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())
    want = norm(wanted)
    return len(want & norm(heard)) / len(want) if want else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
