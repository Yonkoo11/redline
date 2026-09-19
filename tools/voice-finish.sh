#!/usr/bin/env bash
# Finish a human voice take: clean it, level it to broadcast loudness, and time the captions
# off the actual audio rather than off a word count.
#
#   bash tools/voice-finish.sh demo/vo-raw.m4a demo/vo
#
# Writes demo/vo.m4a (the take, cleaned and levelled) and demo/vo.json (Whisper segments with
# start and end in seconds). Nothing here compresses, gates or de-breathes the take: a gate is
# what removes the breaths, and missing breaths are the thing that makes a voice sound machine
# made. The only changes are a rumble filter and a level match.
set -euo pipefail

IN="${1:?usage: voice-finish.sh <raw-recording> <output-stem>}"
STEM="${2:?usage: voice-finish.sh <raw-recording> <output-stem>}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Rumble and handling noise below the male voice fundamental. Nothing musical lives down there.
ffmpeg -y -loglevel error -i "$IN" -af "highpass=f=80" -ar 44100 "$TMP/clean.wav"

# EBU R128, two passes. One pass guesses; two passes measure and then correct.
M=$(ffmpeg -hide_banner -i "$TMP/clean.wav" -af loudnorm=I=-20:TP=-1.5:LRA=11:print_format=json \
      -f null /dev/null 2>&1 | sed -n '/^{/,/^}/p')
get() { printf '%s' "$M" | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

ffmpeg -y -loglevel error -i "$TMP/clean.wav" -af \
  "loudnorm=I=-20:TP=-1.5:LRA=11:measured_I=$(get input_i):measured_TP=$(get input_tp):measured_LRA=$(get input_lra):measured_thresh=$(get input_thresh):offset=$(get target_offset):linear=true" \
  -ar 44100 -c:a aac -b:a 192k "$STEM.m4a"

whisper "$STEM.m4a" --model base --language en --output_format json \
  --output_dir "$(dirname "$STEM")" >/dev/null 2>&1
mv "$(dirname "$STEM")/$(basename "$STEM").json" "$STEM.json" 2>/dev/null || true

python3 - "$STEM.json" <<'PY'
import json, sys
segs = json.load(open(sys.argv[1]))["segments"]
print(f"{len(segs)} caption segments, {segs[-1]['end']:.2f}s")
for s in segs:
    print(f"  {s['start']:6.2f} -> {s['end']:6.2f}  {s['text'].strip()}")
print("\nRead every line above against what you actually said. Whisper spells product names")
print("the way it hears them: it wrote 'Red line' for Redline on the test take.")
PY
echo
echo "levelled: $STEM.m4a"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$STEM.m4a"
