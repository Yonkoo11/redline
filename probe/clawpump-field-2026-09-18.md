# The ClawPump field, measured 2026-09-18

The raw API dump this came from is kept out of the repository, because a published plugin gets
scanned on install and a 200-token JSON blob trips a credential detector on a base58 string. The
numbers are here, and so is the command that reproduces them.

    curl -s 'https://clawpump.tech/api/tokens?limit=200' > tokens.json

| measurement | value |
|---|---|
| tokens in the sample | 200, the newest at the time |
| launched since 2026-08-19 | 184 |
| describing a trading agent | 111 (case-insensitive match on trading-agent wording in the description; a looser match on "agent" alone gives 135) |
| launch platform pump_fun | 198 |
| launch platform meteora_dbc | 1 |
| launch platform pons_v2 | 1 |

Self-hosted harness users are far fewer than the token count suggests: `Clawpump/claw-agent` showed
9 stars and 5 forks on the same date. That gap is the honest market-size risk, and it is named in
`ai/plan.md` rather than hidden.
