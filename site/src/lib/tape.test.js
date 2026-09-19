// node --test site/src/lib/
//
// Run against the committed tape and against record shapes that do not exist yet. The bug this
// guards was a record with no `intent`, which threw inside a Svelte each-block and rendered the
// tape and the policy below it as empty headings on the live site.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { describe as say, isOperator, money, shortSig, verdictOf, whenUTC } from "./record.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const TAPE = join(HERE, "..", "..", "..", "data", "tape.jsonl");

const realRecords = readFileSync(TAPE, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l));

test("the committed tape has records to check", () => {
  assert.ok(realRecords.length > 0);
});

test("every real record renders without throwing, and says something", () => {
  for (const r of realRecords) {
    const line = say(r);
    assert.equal(typeof line, "string");
    assert.ok(line.length > 0, `empty description for ${JSON.stringify(r).slice(0, 120)}`);
    assert.ok(["Operator", "Watched", "Allowed", "Refused"].includes(verdictOf(r)));
  }
});

test("an operator action is not dressed as a verdict on an order", () => {
  const r = { tool: "operator:day_reset", rule: "day_reset", allowed: true };
  assert.equal(verdictOf(r), "Operator");
  assert.equal(say(r), "Day rebaselined");
  assert.equal(say({ tool: "operator:halt_clear", rule: "halt_clear" }), "Halt cleared");
});

test("a record with no order at all is survivable", () => {
  assert.equal(say({ rule: "internal_error", allowed: false }), "Redline could not decide");
  assert.equal(say({ allowed: true }), "Order");
  assert.equal(say({}), "Order");
});

test("a record shape that does not exist yet still renders", () => {
  assert.equal(say({ intent: { kind: "teleport", market: "SOL" } }), "teleport, SOL");
  assert.equal(say({ intent: {} }), "Order");
  assert.equal(verdictOf({ tool: "operator:something_new" }), "Operator");
});

test("every governed kind has a word a person would use", () => {
  for (const kind of ["perp", "swap", "transfer", "withdraw", "spend"]) {
    const line = say({ intent: { kind, notional_usd: 12.5 } });
    assert.ok(!line.includes(kind), `${kind} is being shown raw: ${line}`);
    assert.ok(line.includes("$12.50"));
  }
});

test("a broken number never reaches the page", () => {
  assert.equal(money(undefined), "");
  assert.equal(money(NaN), "");
  assert.equal(money("nonsense"), "");
  assert.equal(money(3.14159), "$3.14");
  assert.equal(say({ intent: { kind: "swap", notional_usd: NaN } }), "Swap");
  assert.equal(say({ intent: { kind: "swap", notional_usd: Infinity } }), "Swap");
});

test("a broken timestamp never reaches the page", () => {
  assert.equal(whenUTC(undefined), "");
  assert.equal(whenUTC("nonsense"), "");
  assert.ok(whenUTC(1789802218).endsWith("UTC"));
});

test("a short or missing signature does not blow up the receipt link", () => {
  assert.equal(shortSig(undefined), "");
  assert.equal(shortSig("abc"), "abc");
  assert.ok(shortSig("a".repeat(88)).includes("…"));
});

test("isOperator does not trip over a missing tool name", () => {
  assert.equal(isOperator({}), false);
  assert.equal(isOperator({ tool: null }), false);
  assert.equal(isOperator({ tool: "mcp_clawpump_swap_execute" }), false);
});
