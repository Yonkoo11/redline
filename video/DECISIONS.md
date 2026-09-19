# DECISIONS — Redline announcement video
Written 2026-09-19 under the demo-video skill's deferred-decisions pattern. Five decisions, each
with what it cost and how to undo it.

## Decision: ffmpeg, not Remotion
**Chosen:** `tools/build-video.py` + `tools/captions.py` + `tools/burn-captions.py`.
**Why:** Remotion exists to sequence animated React scenes. All seven segments here are real
captures — two terminal recordings and five browser recordings — with no animated scene in the
cut. Remotion would be a large install to concatenate files and burn captions.
**Cost:** no Remotion Studio, so subtitle timing is verified by reading the printed transcript and
scrubbing the output rather than dragging a playhead.
**Undo:** scaffold `video/` per the skill and port `demo/edit.json` into `SCENE_DURATIONS`.

## Decision: PLAYBACK_RATE 1.0, not the skill's 1.2
**Chosen:** nothing is sped up. No `atempo` either.
**Why:** shot 3 is 27.5 seconds of real network waiting on mainnet, and the waiting is the
evidence the run is real. Speeding it a fifth throws that away, and a voice pitched up a fifth
stops sounding like a person in a room. The skill warns against stacking both speedup mechanisms;
taking neither is inside that warning.
**Undo:** `PLAYBACK_RATE` in the skill's constants, or a `--speed` flag on build-video.py.

## Decision: Gemini TTS, after I misread the brief
**Chosen:** Gemini `Charon`, one call per segment, atempo 1.12.
**What I got wrong:** the operator said "I do not want an AI slop or obvious AI generated voice"
and "avoid macos voice generator". That is a quality bar. I read it as a ban on synthetic voice
altogether, built the whole plan around needing a human take, and put the same question to them
twice. Their actual position: a synthetic voice is fine if it does not sound like slop.
**Departure from the skill:** the skill says generate the whole narration in ONE call and slice it
at the silences, for consistent prosody. That was tried three times. Each run placed its pauses
differently; on the third the slices carried the wrong lines, with segment 4a reading segment 3's
closing sentence. So: one call per segment, and every piece is transcribed and matched against the
line it should carry before anything is kept. Prosody drifts slightly between segments. Wrong
words over the wrong picture is worse.
**Two things the verification caught that a listen might not have:** the model read
useredline.xyz as "Redline.xyz", dropping the "use" from the one URL in the video; and it said
"Clarina" for Clawrena, the event's own name, twice, including after a phonetic respelling. Both
lines were rewritten so the screen carries those words instead of the voice.
**Undo:** `demo/narration.json` holds the script; `tools/tts.py <id>` regenerates one segment.

## Decision: captions drawn as images, not burned by ffmpeg
**Chosen:** `tools/burn-captions.py` draws each caption with Pillow and overlays it.
**Why:** this machine's ffmpeg is built without libass, so it has neither a `subtitles` filter nor
`drawtext`. Found by running it, not by reading a manpage.
**Cost:** one overlay filter per caption. 27 captions rendered in one pass without complaint.
**Undo:** install an ffmpeg with libass and use the normal filter.

## Decision: no vertical social clip
**Chosen:** dropped.
**Why:** the skill asks for a 1080x1920 clip. Playwright records a page at CSS pixels and pads the
rest of the frame, so asking for 1080x1920 put the 390-wide phone layout in the corner of a grey
canvas. Cropping the real region and upscaling 2.8x is visibly soft on type. A soft asset is worse
than no asset, and the 1920x1080 cut plays fine in an X timeline.
**Undo:** a headless browser that renders at device pixels, or design a vertical frame rather than
rescaling a phone screenshot.

## Not applicable
**Pitch deck.** The skill says generate one only when the submission platform requires it.
AnsemHack asks for a 15-minute stream with four questions, not a deck. Skipped.

## Decision: ship a captions-only cut now, voice cut as the upgrade
**Chosen:** `demo/redline-captioned.mp4` — 93.3s, 1920x1080, 22 text cards, no audio track.
**Why:** the only acceptable voice is the user's own, and that is the one thing a tool cannot
produce. Leaving the deliverable at "silent preview, waiting on you" is a half-finished thing; a
captioned silent cut is a finished one. Most of a timeline is watched muted anyway.
**Timing method:** reading speed, not Whisper, because there is no audio to derive timing from.
Deriving caption times from a word count while someone IS speaking is what the pipeline forbids,
and this is not that. Cards in the terminal take carry explicit cues at 7.4s, 10.4s, 17.2s and
24.4s, the measured moments the screen actually changes, because a card saying the balance was
read while the terminal is still empty is a lie told by timing.
**Guard:** `tools/cards.py` refuses to build if a card would be squeezed by more than a tenth of
its readable span to fit a fixed shot. It refused once, on the last card of the terminal take,
and the line was shortened rather than the take cut.
**Undo:** record the seven voice takes and run the voice chain; the cards become subtitles timed
off Whisper instead.
