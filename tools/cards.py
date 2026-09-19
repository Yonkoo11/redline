"""Build the captions-only cut: on-screen text, no voice.

A silent video with text is a finished thing, not a half-finished one: most of a timeline is
watched muted. It is not a substitute for the voice cut, it is the version that exists today.

Timing here is reading speed, not Whisper, because there is no audio to derive it from. That is
the honest method when nothing is being said; deriving caption times from a word count while
someone IS speaking is the thing the pipeline forbids, and this is not that.

  python3 tools/cards.py          # size the shots to the reading, rebuild, write the SRT
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

DEMO = Path("demo")


def stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> int:
    spec = json.loads((DEMO / "cards.json").read_text())
    cards, cps, floor = spec["cards"], spec["read_chars_per_second"], spec["min_card_seconds"]
    edit = json.loads((DEMO / "edit.json").read_text())

    # A card needs long enough to read. A shot needs long enough for its cards, plus a beat at
    # the end so the last line does not vanish on the cut.
    def text_of(card):
        return card["text"] if isinstance(card, dict) else card

    def cue_of(card):
        return card.get("at") if isinstance(card, dict) else None

    plan = {}
    for shot in edit["shots"]:
        lines = [text_of(c) for c in cards.get(shot["id"], [])]
        spans = [max(floor, len(t) / cps + 0.5) for t in lines]
        plan[shot["id"]] = spans
        if not shot.get("fixed"):
            shot["min"] = round(sum(spans) + 0.8, 2)
        elif spans:
            # A fixed shot runs its own length and the text has to fit inside it. Shot 3 is the
            # one that matters: its length is 27.5 seconds of real network waiting.
            #
            # Summing the spans is not enough once cards carry cues: a cue pushes a card later,
            # so the last one can end past the shot even when the total fits. Walk it the way it
            # will actually play.
            room = _target_of(shot, {shot["id"]: spans})
            at, end = 0.0, 0.0
            for card, span in zip(cards[shot["id"]], spans):
                cue = cue_of(card)
                at = max(at, cue) if cue is not None else at
                end = at + span
                at = end
            # Losing a fraction of a second off the last card is not worth a rewrite; losing a
            # readable share of it is. Ten per cent of one card's span is the line.
            if end - room > 0.1 * spans[-1]:
                raise SystemExit(
                    f"{shot['id']}: the last card ends at {end:.1f}s and the shot runs "
                    f"{room:.1f}s. Cut words, not the take.")
    (DEMO / "edit.json").write_text(json.dumps(edit, indent=2) + "\n")

    shot_len = {s["id"]: _target_of(s, plan) for s in edit["shots"]}
    subprocess.run(["python3", "tools/build-video.py"], check=True)
    timeline = json.loads((DEMO / "timeline.json").read_text())

    # build-video writes voice offsets; with no voice it writes none, so walk the shots instead.
    offsets, t = {}, 0.0
    for shot in edit["shots"]:
        offsets[shot["id"]] = t
        t += shot["_target"] if "_target" in shot else 0
    if not any(offsets.values()):
        offsets, t = {}, 0.0
        for shot in edit["shots"]:
            offsets[shot["id"]] = t
            t += _target_of(shot, plan)

    out, n = [], 0
    for shot in edit["shots"]:
        base = offsets[shot["id"]]
        at = 0.0
        for card, span in zip(cards.get(shot["id"], []), plan[shot["id"]]):
            cue = cue_of(card)
            # A cue pins a card to the moment on screen it describes. It never pulls a card
            # earlier than the one before it has finished being readable.
            at = max(at, cue) if cue is not None else at
            # A card never outlives its shot: the next shot's first card would collide with it.
            end = min(at + span, shot_len[shot["id"]])
            n += 1
            out.append(f"{n}\n{stamp(base + at)} --> {stamp(base + end)}\n{text_of(card)}\n")
            at = end
    (DEMO / "captions.srt").write_text("\n".join(out))
    print(f"  {n} cards -> demo/captions.srt over {timeline['total']:.1f}s")
    return 0


def _target_of(shot, plan):
    if shot.get("fixed"):
        clip = Path(shot["clip"])
        if clip.suffix == ".cast":
            ev = [json.loads(l) for l in clip.read_text().splitlines() if l.startswith("[")]
            return round(ev[-1][0], 2) + 3.0
    return max(sum(plan[shot["id"]]) + 0.8, shot.get("min", 3.0))


if __name__ == "__main__":
    raise SystemExit(main())
