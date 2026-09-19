// Publishes the agent's tape into the site.
//
// On the machine running the agent, the live tape is at ~/.hermes/redline/tape.jsonl. That file
// cannot exist on a build server, so this script also writes a snapshot to data/tape.jsonl, which
// IS committed. CI has no live tape and therefore publishes the snapshot. Source of each build is
// recorded in the output so the page never implies more freshness than it has.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const agentHome = process.env.REDLINE_HOME || join(homedir(), ".hermes", "redline");
const liveTape = process.env.REDLINE_TAPE || join(agentHome, "tape.jsonl");
const snapshot = "../data/tape.jsonl";
const snapshotPolicy = "../data/policy.json";

const parse = (p) => readFileSync(p, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l));

// Only decisions taken against a real balance are published. A test that hands the plugin a made
// up balance writes to the same tape, and those rows are not evidence of anything: a refusal
// decided from a number nobody held proves nothing, and on a public page it reads as though it
// did. Until now this was done by hand, which is why twelve fixture rows were sitting in the live
// tape waiting for the next publish to pick them up.
const isReal = (r) => r.equity_source === "live";

let rows, policy, source;
if (existsSync(liveTape)) {
  const all = parse(liveTape);
  rows = all.filter(isReal);
  if (all.length !== rows.length) {
    console.log(`tape: ${all.length - rows.length} fixture-equity rows held back, not published`);
  }
  policy = existsSync(join(agentHome, "policy.json")) ? JSON.parse(readFileSync(join(agentHome, "policy.json"), "utf8")) : {};
  source = "live agent tape";
  mkdirSync("../data", { recursive: true });
  writeFileSync(snapshot, rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  writeFileSync(snapshotPolicy, JSON.stringify(policy, null, 1));
} else if (existsSync(snapshot)) {
  rows = parse(snapshot).filter(isReal);
  policy = existsSync(snapshotPolicy) ? JSON.parse(readFileSync(snapshotPolicy, "utf8")) : {};
  source = "committed snapshot";
} else {
  rows = []; policy = {}; source = "none";
}

writeFileSync("public/tape.json", JSON.stringify({ generated_at: new Date().toISOString(), source, policy, rows }, null, 1));
console.log(`tape: ${rows.length} records from the ${source} -> public/tape.json`);
