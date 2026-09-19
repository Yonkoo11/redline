"""Record a command's terminal session to an asciicast v2 file.

Uses the standard library pty, so the recording is the real terminal the command wrote to,
not a picture of a window. Nothing outside the pty is captured, which is the point: a window
grab has twice leaked an unrelated project.

  python3 tools/record-terminal.py out.cast -- bash run-venue-gate.sh --execute

Render it:
  agg --font-size 28 --idle-time-limit 60 out.cast out.gif   # the default caps waits at 5s
  ffmpeg -i out.gif -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1:color=0x1e1e1e" \
         -c:v libx264 -pix_fmt yuv420p -r 30 out.mp4
"""
import json, os, pty, sys, time

# 140 wide because a Solana signature is 88 characters and at 120 the solscan URL
# wrapped onto a second line in the middle of the take.
COLS, ROWS = 140, 32

if "--" not in sys.argv:
    sys.exit(__doc__)
split = sys.argv.index("--")
out_path = sys.argv[1]
argv = sys.argv[split + 1:]
if not argv:
    sys.exit("nothing to run")

start = time.time()
out = open(out_path, "w")
out.write(json.dumps({
    "version": 2, "width": COLS, "height": ROWS,
    "timestamp": int(start), "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
}) + "\n")


def read(fd):
    data = os.read(fd, 65536)
    if data:
        out.write(json.dumps([round(time.time() - start, 6), "o",
                              data.decode("utf-8", "replace")]) + "\n")
        out.flush()
    return data


env = dict(os.environ, TERM="xterm-256color", COLUMNS=str(COLS), LINES=str(ROWS), PS1="$ ")
os.environ.update(env)
code = pty.spawn(argv, read)
out.close()
print(f"{out_path}: {round(time.time() - start, 1)}s, exit {code >> 8}", file=sys.stderr)
sys.exit(code >> 8)
