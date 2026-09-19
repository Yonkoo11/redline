// Copies the agent's tape into the site so the page can show real records.
// Run before `npm run build`. Reads ~/.hermes/redline/tape.jsonl, writes public/tape.json.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const src = process.env.REDLINE_TAPE || join(homedir(), ".hermes", "redline", "tape.jsonl");
const rows = existsSync(src)
  ? readFileSync(src, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l))
  : [];
const policy = existsSync(join(homedir(), ".hermes", "redline", "policy.json"))
  ? JSON.parse(readFileSync(join(homedir(), ".hermes", "redline", "policy.json"), "utf8"))
  : {};
writeFileSync("public/tape.json", JSON.stringify({ generated_at: new Date().toISOString(), policy, rows }, null, 1));
console.log(`tape: ${rows.length} records -> public/tape.json`);
