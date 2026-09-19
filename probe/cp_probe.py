import json, os, sys, urllib.request
KEY = os.getenv("CLAWPUMP_API_KEY")
if not KEY: sys.exit("no key in env")
def get(url):
    r = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + KEY,
        "User-Agent": "redline-probe/1.0",
        "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            return resp.status, resp.read()[:1500].decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)[:200]
for u in sys.argv[1:]:
    s, b = get(u)
    print(f"--- {u}\n{s}  {b}\n")
