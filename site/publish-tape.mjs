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

let rows, policy, source;
if (existsSync(liveTape)) {
  rows = parse(liveTape);
  policy = existsSync(join(agentHome, "policy.json")) ? JSON.parse(readFileSync(join(agentHome, "policy.json"), "utf8")) : {};
  source = "live agent tape";
  mkdirSync("../data", { recursive: true });
  writeFileSync(snapshot, rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  writeFileSync(snapshotPolicy, JSON.stringify(policy, null, 1));
} else if (existsSync(snapshot)) {
  rows = parse(snapshot);
  policy = existsSync(snapshotPolicy) ? JSON.parse(readFileSync(snapshotPolicy, "utf8")) : {};
  source = "committed snapshot";
} else {
  rows = []; policy = {}; source = "none";
}

writeFileSync("public/tape.json", JSON.stringify({ generated_at: new Date().toISOString(), source, policy, rows }, null, 1));
console.log(`tape: ${rows.length} records from the ${source} -> public/tape.json`);
