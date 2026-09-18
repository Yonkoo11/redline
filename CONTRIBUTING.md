# Contributing

Redline is a policy layer on a money path, so the bar for a change is: does the refusal still happen, and can a stranger see that it did?

- Run `python3 -m unittest discover -s tests -t .` before opening a pull request. Add a test for every new rule or every new tool-argument shape you teach `redline/intent.py` to read.
- Never weaken fail-closed behaviour. If a value cannot be read or priced, the answer is refuse.
- Never commit keys, keypair files, or `.env` files. The tape keypair lives outside the repository.
- Real venue argument shapes go in `probe/` with the date they were observed. Do not guess an envelope.
- Keep functions under 30 lines. No new dependencies in `redline/` without a reason in the pull request.
