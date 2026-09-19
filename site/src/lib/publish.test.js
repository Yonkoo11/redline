// node --test site/src/lib/
//
// The publisher's one job that is not mechanical: a decision taken against a made-up balance must
// never reach the public page. Twelve such rows accumulated in the live tape in a single day from
// integration runs, and nothing in the build would have stopped them going out.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function publish(rows) {
  const home = mkdtempSync(join(tmpdir(), "redline-tape-"));
  writeFileSync(join(home, "tape.jsonl"), rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  writeFileSync(join(home, "policy.json"), "{}");
  const out = join(home, "out");
  mkdirSync(join(out, "public"), { recursive: true });
  mkdirSync(join(out, "data"), { recursive: true });
  execFileSync("node", [join(SITE, "publish-tape.mjs")], {
    cwd: join(out, "public", ".."),
    env: { ...process.env, REDLINE_HOME: home },
  });
  const published = JSON.parse(readFileSync(join(out, "public", "tape.json"), "utf8"));
  rmSync(home, { recursive: true, force: true });
  return published.rows;
}

const real = { ts: 1, allowed: false, equity_usd: 15.85, equity_source: "live", rule: "trade_cap" };
const fake = { ts: 2, allowed: false, equity_usd: 100.0, equity_source: "fixture", rule: "trade_cap" };

test("a decision taken against a made-up balance is never published", () => {
  const rows = publish([real, fake]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].equity_source, "live");
});

test("a row with no equity_source at all is treated as not real", () => {
  const rows = publish([real, { ts: 3, allowed: true }]);
  assert.equal(rows.length, 1);
});
