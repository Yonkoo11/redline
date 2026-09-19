// How a tape record becomes words.
//
// This lives outside the components because it broke the site once. The tape grew two record
// shapes that carry no order at all, an operator action and an internal error, and the page read
// straight through `record.intent.market`. That threw, and a throw inside a Svelte each-block
// takes the whole list with it, so the tape and the policy below it rendered as empty headings on
// the live site. Nothing in the build or the tests could see it, because neither renders a page.
//
// Every function here tolerates a record it has never seen. `tape.test.js` feeds it the real tape
// plus the shapes a future version might write.

export const KINDS = {
  perp: "Perpetual",
  swap: "Swap",
  transfer: "Transfer",
  withdraw: "Withdrawal",
  spend: "Payment",
};

export const isOperator = (r) => String(r?.tool ?? "").startsWith("operator:");

export function verdictOf(r) {
  if (isOperator(r)) return "Operator";
  if (r?.would_refuse) return "Watched";
  return r?.allowed ? "Allowed" : "Refused";
}

/** One line naming what was judged, for any record shape. Never throws. */
export function describe(r) {
  if (isOperator(r)) {
    if (r.rule === "day_reset") return "Day rebaselined";
    if (r.rule === "halt_clear") return "Halt cleared";
    return "Operator action";
  }
  if (r?.rule === "internal_error") return "Redline could not decide";

  const intent = r?.intent;
  if (!intent) return "Order";

  const parts = [KINDS[intent.kind] ?? intent.kind ?? "Order"];
  if (intent.market) parts.push(String(intent.market));
  if (Number.isFinite(intent.notional_usd) && intent.notional_usd) {
    parts.push(`$${Number(intent.notional_usd).toFixed(2)} notional`);
  }
  return parts.join(", ");
}

export const money = (n) =>
  n === null || n === undefined || !Number.isFinite(Number(n))
    ? ""
    : `$${Number(n).toFixed(2)}`;

export const whenUTC = (ts) =>
  Number.isFinite(Number(ts))
    ? new Date(Number(ts) * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC"
    : "";

export const shortSig = (s) =>
  typeof s === "string" && s.length > 18 ? s.slice(0, 10) + "…" + s.slice(-6) : (s ?? "");
