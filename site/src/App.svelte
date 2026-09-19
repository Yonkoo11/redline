<script>
  import Shell from "./lib/Shell.svelte";
  import { describe as what, isOperator, money, shortSig as short, verdictOf, whenUTC as when } from "./lib/record.js";
  const RPC = "https://solana-rpc.publicnode.com";
  const AGENT = "FT5GaRv2eV74aS3dTPw6ZNsVBackGTW9dNQfw4jSZirz";
  const SOL = "So11111111111111111111111111111111111111112";
  const REST = -42, HARD = 64;

  // The home page carries the most recent verdicts; /log/ is the full reader.
  const SHOWN = 8;
  let tape = $state([]);
  let policy = $state(null);

  // The operator public key these published limits are signed with. Public by design: it is what
  // lets a reader check the signature without asking us for anything.
  const OPERATOR_KEY = "AqRT7dJrWw4t5vcgDDh9NosgFZKSMYhywxCvHFnJTwjm";

  // The project token. Listed here because a reader who wants it should not have to hunt, and
  // because nothing on this page depends on it: the tool works with the token ignored.
  const MINT = "DCma6fRtqQJdPXsxr8wmZzNvqbGzKxuBaAQYoeQyjohs";
  let equity = $state(null);
  let failed = $state(false);
  let copied = $state(false);

  const refusals = $derived(tape.filter((r) => !r.allowed));
  const lastRefusal = $derived(refusals[0] ?? null);
  const cap = $derived(equity === null ? null : equity * 0.1);
  // The needle's position is real: it comes from the refusal on the tape measured against the
  // cap in force when that order was judged. Only the MOMENT is choreographed. On a fast
  // connection the balance lands in under half a second, and a sweep nobody sees is a sweep that
  // may as well not exist, so the needle is held at rest until the page has finished arriving.
  let settled = $state(false);
  const needle = $derived.by(() => {
    if (!settled || equity === null || !lastRefusal) return REST;
    const ratio = (lastRefusal.intent?.notional_usd ?? 0) / (lastRefusal.equity_usd * 0.1 || 1);
    return Math.max(REST, Math.min(HARD, REST + (106 * ratio) / 9));
  });


  if (typeof window !== "undefined") {
    const hold = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1180;
    setTimeout(() => (settled = true), hold);
  }

  fetch("tape.json")
    .then((r) => r.json())
    .then((d) => { tape = [...d.rows].reverse(); policy = d.policy; });

  // Equity is SOL plus every token the wallet holds, not SOL alone. Reading only the native
  // balance under-reported this wallet by its whole USDC position, and got worse with every swap
  // the agent made, because a swap turns SOL into exactly the thing that was not counted. The
  // plugin has always counted both. This page did not, and this page is the number people read.
  //
  // The native balance still comes from a Solana RPC, so "read from Solana" stays true of it.
  // Token balances do not: every public RPC tried blocks getTokenAccountsByOwner from a browser
  // (publicnode "Request blocked", mainnet-beta "Access forbidden", drpc paid-plan only), so they
  // come from Jupiter, which is already the price source. The caption under the number says so.
  //
  // If a held token cannot be read or cannot be priced, the reading fails and the page says
  // unavailable. It does not fall back to SOL alone: a cap derived from a balance that is missing
  // a position is not a cap, and a number that is quietly wrong is worse than no number.
  const DUST = 1e-9;

  (async () => {
    try {
      const [bal, held] = await Promise.all([
        fetch(RPC, { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getBalance", params: [AGENT] }),
        }).then((r) => r.json()),
        fetch(`https://lite-api.jup.ag/ultra/v1/balances/${AGENT}`).then((r) => {
          if (!r.ok) throw new Error(`balances ${r.status}`);
          return r.json();
        }),
      ]);

      const tokens = Object.entries(held)
        .filter(([mint, v]) => mint !== "SOL" && Number(v.uiAmount) >= DUST)
        .map(([mint, v]) => [mint, Number(v.uiAmount)]);

      const ids = [SOL, ...tokens.map(([mint]) => mint)].join(",");
      const px = await fetch(`https://lite-api.jup.ag/price/v3?ids=${ids}`).then((r) => r.json());
      if (!px[SOL]?.usdPrice) throw new Error("no SOL price");

      let total = (bal.result.value / 1e9) * px[SOL].usdPrice;
      for (const [mint, amount] of tokens) {
        const price = px[mint]?.usdPrice;
        if (!price) throw new Error(`no price for ${mint}`);
        total += amount * price;
      }
      equity = total;
    } catch { failed = true; }
  })();

  async function copy() {
    await navigator.clipboard.writeText("hermes plugins install Yonkoo11/redline && hermes plugins enable redline");
    copied = true;
    setTimeout(() => (copied = false), 1600);
  }
</script>

<Shell here="home">

  <div class="state" data-reveal style="--rv-delay:130ms; --rv-dur:520ms">
    <span class="dot" aria-hidden="true"></span>
    <span><b>Holding.</b> {tape.length} orders judged, {refusals.length} refused, and every refusal is on chain.</span>
  </div>

  <section class="first">
    <div>
      <h1 data-reveal style="--rv-delay:250ms; --rv-dur:520ms">Kill switch for <em>claw traders</em>.</h1>
      <p class="sub" data-reveal style="--rv-delay:430ms; --rv-dur:560ms">
        An agent may trade as hard as it likes, right up to the line. It cannot cross it. Redline sits
        between the model and the wallet: every order passes the policy its operator signed, or it is
        refused and the refusal is written to Solana.
      </p>
      <p class="claim" data-reveal style="--rv-delay:580ms; --rv-dur:560ms">
        <b>111 of the 200 newest tokens on ClawPump describe a trading agent.</b>
        The platform gives them a daily model-spend budget and an address whitelist. No per-order cap.
        No daily loss limit. No drawdown halt.
        <cite>Measured from clawpump.tech, 18 September 2026</cite>
      </p>
    </div>

    <div class="housing" data-reveal style="--rv-delay:300ms; --rv-dur:720ms">
      <svg class="dial" viewBox="0 0 520 300" role="img" aria-label="The agent's live equity against the cap the policy derives from it">
        <defs>
          <linearGradient id="face" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#F7F6F2" /><stop offset="1" stop-color="#E4E1D9" />
          </linearGradient>
        </defs>
        <path d="M 40 270 A 220 220 0 0 1 480 270" fill="url(#face)" stroke="rgba(19,20,23,.16)" stroke-width="2" />
        <g stroke="rgba(19,20,23,.45)" stroke-width="2">
          <line x1="40" y1="270" x2="70" y2="270" /><line x1="450" y1="270" x2="480" y2="270" />
          <line x1="66" y1="182" x2="94" y2="193" /><line x1="454" y1="182" x2="426" y2="193" />
          <line x1="124" y1="110" x2="144" y2="132" /><line x1="396" y1="110" x2="376" y2="132" />
          <line x1="205" y1="64" x2="214" y2="92" /><line x1="315" y1="64" x2="306" y2="92" />
          <line x1="260" y1="50" x2="260" y2="80" />
        </g>
        <path d="M 372 96 A 220 220 0 0 1 480 270" fill="none" stroke="#E03A2F" stroke-width="16" />
        <g class="needle" class:live={equity !== null} style="--deg:{needle}deg">
          <path d="M252 258 L268 258 L263 72 L257 72 Z" fill="#131417" />
          <circle cx="260" cy="270" r="17" fill="#131417" />
          <circle cx="260" cy="270" r="5" fill="#E4E1D9" />
        </g>
      </svg>

      <div class="readout">
        <div>
          <span class="lbl">Agent equity, live</span>
          <div class="val">{failed ? "unavailable" : equity === null ? "reading…" : money(equity)}</div>
          <div class="note">
            {failed
              ? "Solana RPC or the price feed did not answer. The tape below is unaffected."
              : "FT5GaRv2…jSZirz, SOL read from Solana and tokens from Jupiter, in your browser"}
          </div>
        </div>
        <div>
          <span class="lbl">Cap per order</span>
          <div class="val red">{cap === null ? "—" : money(cap)}</div>
          <div class="note">10% of equity, from the signed policy</div>
        </div>
      </div>

      {#if lastRefusal}
        <div class="proof">
          <span class="verdict refused">Refused</span>
          <div>
            <div class="what">{lastRefusal.intent.kind === "perp" ? "Perpetual" : "Swap"}, <b>{lastRefusal.intent.market}</b>, <span class="nb">{money(lastRefusal.intent.notional_usd)} notional</span></div>
            <div class="why">{lastRefusal.reason}</div>
          </div>
          {#if lastRefusal.memo_sig}
            <a class="receipt" href={`https://solscan.io/tx/${lastRefusal.memo_sig}`}>{short(lastRefusal.memo_sig)} ↗</a>
          {/if}
        </div>
      {/if}
    </div>
  </section>

  <div class="section-head">
    <h2>The tape</h2><span class="lbl">newest first. only refusals get a receipt</span>
  </div>

  {#each tape.slice(0, SHOWN) as r}
    <div class="rec" class:refused={!r.allowed} class:watched={r.would_refuse}
         class:operator={isOperator(r)}>
      <span class="verdict" class:refused={!r.allowed && !isOperator(r)}
            class:allowed={r.allowed && !r.would_refuse && !isOperator(r)}
            class:watched={r.would_refuse} class:operator={isOperator(r)}>
        {verdictOf(r)}
      </span>
      <div>
        <div class="what">{what(r)}</div>
        <div class="why">{r.reason}{#if r.would_refuse}. Watching only, so the order went through{/if}</div>
        <div class="meta">
          <span>{when(r.ts)}</span>
          {#if r.equity_usd}<span>equity {money(r.equity_usd)}, read {r.equity_source}</span>{/if}
        </div>
      </div>
      <div class="side">
        {#if r.memo_sig}
          <a class="receipt" href={`https://solscan.io/tx/${r.memo_sig}`}>{short(r.memo_sig)} ↗</a>
        {/if}
      </div>
    </div>
  {/each}

  {#if tape.length > SHOWN}
    <a class="more" href="./log/">
      Read all {tape.length} verdicts, with the reason for each <span aria-hidden="true">→</span>
    </a>
  {/if}

  <div class="section-head">
    <h2>The policy</h2><span class="lbl">signed by the operator, enforced on every call</span>
  </div>
  {#if policy}
    <div class="policy">
      <div class="lim"><span class="n">Per-order cap</span><span class="v red">{policy.max_trade_pct_equity}% of equity</span></div>
      <div class="lim"><span class="n">Daily loss limit</span><span class="v">{policy.max_daily_loss_pct}%</span></div>
      <div class="lim"><span class="n">Drawdown halt</span><span class="v red">{policy.max_drawdown_pct}%</span></div>
      <div class="lim"><span class="n">Maximum leverage</span><span class="v">{policy.max_leverage}×</span></div>
      <div class="lim"><span class="n">Markets</span><span class="v">{policy.allowed_markets.join(", ")}</span></div>
      <div class="lim"><span class="n">Swap tokens</span><span class="v">{policy.allowed_tokens.join(", ")}</span></div>
      <div class="lim"><span class="n">Daily turnover budget</span><span class="v">{policy.max_daily_notional_pct_equity ?? 300}% of equity</span></div>
      <div class="lim"><span class="n">Payment limit</span><span class="v">${policy.max_spend_usd ?? 1}</span></div>
      <div class="lim"><span class="n">Transfer destinations</span><span class="v">allowlist only</span></div>
      <div class="lim"><span class="n">Transfer limit</span><span class="v red">{(policy.max_transfer_usd ?? 0) === 0 ? "none allowed" : `$${policy.max_transfer_usd}`}</span></div>
      <div class="lim"><span class="n">Collateral withdrawals</span><span class="v red">always refused</span></div>
      <div class="lim"><span class="n">Equity unreadable</span><span class="v red">refuse</span></div>
      <div class="lim"><span class="n">Policy unsigned or altered</span><span class="v red">refuse</span></div>
    </div>

    {#if policy.signature}
      <div class="sig">
        <div class="sig-row">
          <span class="lbl">Operator key</span>
          <code>{OPERATOR_KEY}</code>
        </div>
        <div class="sig-row">
          <span class="lbl">Signature over these limits</span>
          <code>{policy.signature.slice(0, 22)}…{policy.signature.slice(-8)}</code>
        </div>
        <p class="sig-note">
          The limits above are signed with a key the agent does not hold. Change one number and the
          signature stops matching, and Redline refuses every order until an operator signs again.
          Check it yourself:
        </p>
        <code class="sig-cmd">redline sign check policy.json</code>
      </div>
    {/if}
  {/if}

  <section class="install">
    <h3>Put it in front of your agent</h3>
    <p>Redline is a Hermes plugin. It never holds a key, it refuses when it cannot read the balance, and it is MIT licensed.</p>
    <div class="cmd">
      <code>hermes plugins install Yonkoo11/redline &amp;&amp; hermes plugins enable redline</code>
      <button type="button" onclick={copy} aria-label="Copy the install command">{copied ? "Copied" : "Copy"}</button>
    </div>
    <p class="then">
      Put its commands on your path with
      <code class="inlinecmd">export PATH="$HOME/.hermes/plugins/redline:$PATH"</code>, then
      <a href="./policy/">build your limits</a> and sign them with a key the agent does not
      hold. Run it watching first, with nothing blocked, and read what it would have stopped. The
      <a href="./guide/">guide</a> lists every reason it can refuse and what to do about each one.
    </p>
  </section>

</Shell>

<style>
  h1,h2,h3,.brandword{font-family:"Barlow Condensed",Impact,sans-serif;margin:0}
  .lbl{font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}


  .state{padding:var(--s4) 0;border-bottom:1px solid var(--rule);min-width:0}
  .state b{font-weight:600}
  .dot{display:inline-block;width:8px;height:8px;border-radius:var(--r-full);background:var(--red);margin-right:var(--s3);vertical-align:baseline;animation:beat 2.4s var(--ease) infinite}
  @keyframes beat{0%{box-shadow:0 0 0 0 rgba(224,58,47,.45)}70%{box-shadow:0 0 0 9px rgba(224,58,47,0)}100%{box-shadow:0 0 0 0 rgba(224,58,47,0)}}

  .first{display:grid;grid-template-columns:1fr;gap:var(--s12);padding:var(--s12) 0}
  @media(min-width:900px){.first{grid-template-columns:minmax(0,44%) minmax(0,1fr);gap:var(--s16);align-items:center;padding:var(--s16) 0 var(--s12)}}
  h1{font-weight:800;font-size:clamp(40px,9vw,84px);line-height:.92;letter-spacing:-.022em;overflow-wrap:break-word}
  h1 em{font-style:normal;color:var(--red)}
  .sub{margin:var(--s6) 0 0;max-width:38ch;color:var(--ink-2);line-height:1.55}
  .claim{margin:var(--s6) 0 0;padding-left:var(--s4);border-left:3px solid var(--red);max-width:42ch;font-size:14px;line-height:1.6;color:var(--ink-2)}
  .claim b{color:var(--ink);font-weight:600}
  .claim cite{display:block;margin-top:var(--s2);font-style:normal;font-size:13px;color:var(--ink-3)}

  /* The card answers to its own width, never the page's. Its insides used to re-layout because
     the VIEWPORT crossed 1060px, which is how a three-column proof row ended up squeezed inside a
     568px card on a wide screen. --cu is 1px at the reference width, so a descendant can be sized
     in card units and mean it. */
  .housing{container-type:inline-size; --cu:calc(100cqw / 568);
           position:relative;background:var(--paper-2);border-radius:var(--r-lg);padding:var(--s8) var(--s6) var(--s6);
    box-shadow:var(--e-3), inset 0 1px 0 rgba(255,255,255,.7)}
  .housing::after{content:"";position:absolute;inset:0;border-radius:inherit;padding:1px;
    background:linear-gradient(160deg,rgba(255,255,255,.9),rgba(19,20,23,.16));
    -webkit-mask:linear-gradient(rgba(0,0,0,1) 0 0) content-box,linear-gradient(rgba(0,0,0,1) 0 0);mask-composite:exclude;pointer-events:none}
  .dial{display:block;width:100%;height:auto}
  .needle{transition:transform 900ms var(--ease)}

  /* A gradient hairline that catches light at the top edge and fades by the base, the way a
     pressed metal bezel does. It accompanies the elevation below it; it never replaces it. */
  .housing::before{content:"";position:absolute;inset:0;border-radius:inherit;
    padding:var(--hairline);pointer-events:none;
    background:linear-gradient(168deg, rgba(255,255,255,.9) 0%, rgba(19,20,23,.16) 46%, rgba(19,20,23,.06) 100%);
    -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite:xor; mask-composite:exclude}

  .readout{display:grid;grid-template-columns:minmax(0,1fr);gap:var(--s6);margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--rule)}
  @container (min-width:400px){.readout{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s4)}}
  .readout .val{font:600 clamp(24px,5vw,28px)/1.1 "IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;margin-top:6px;overflow-wrap:anywhere}
  .readout .val.red{color:var(--red)}
  .readout .note{font-size:13px;line-height:1.45;color:var(--ink-3);margin-top:5px}

  .proof{display:grid;grid-template-columns:minmax(0,1fr);gap:var(--s2);align-items:start;
    margin-top:var(--s6);padding:var(--s4);border-radius:var(--r-md);
    background:linear-gradient(90deg,rgba(224,58,47,.075),transparent 62%);box-shadow:inset 3px 0 0 var(--red), var(--e-1)}
  .proof>*{min-width:0}
  .proof .receipt{justify-self:start}
  @container (min-width:400px){.proof{grid-template-columns:auto minmax(0,1fr);gap:var(--s2) var(--s4)}.proof .receipt{grid-column:2}}
  /* Three columns only when the CARD is wide enough to hold them, measured rather than guessed:
     the verdict chip and the receipt link need ~250cu between them before the reason stops wrapping. */
  @container (min-width:640px){.proof{grid-template-columns:auto minmax(0,1fr) auto}
    .proof .receipt{grid-column:3;align-self:center;justify-self:end}}
  .proof .what{font-size:15px}
  .proof .why{font-size:14px;line-height:1.45;color:var(--ink-2);margin-top:4px}

  .section-head{display:flex;align-items:baseline;gap:var(--s4);padding-bottom:var(--s3);border-bottom:2px solid var(--ink);margin-top:var(--s16);flex-wrap:wrap}
  .section-head h2{font-weight:800;font-size:clamp(26px,3vw,36px);line-height:1;letter-spacing:-.01em}
  .section-head .lbl{margin-left:auto}

  .rec{display:grid;grid-template-columns:minmax(0,1fr);gap:var(--s2);padding:var(--s6) 0;border-bottom:1px solid var(--rule)}
  .rec>*{min-width:0}
  @media(min-width:760px){.rec{grid-template-columns:118px minmax(0,1fr) auto;gap:var(--s2) var(--s6)}.rec .side{text-align:right;align-self:center}}
  .rec.refused{background:linear-gradient(90deg,rgba(224,58,47,.055),transparent 56%);box-shadow:inset 3px 0 0 var(--red);padding-left:var(--s4)}
  .verdict{font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;display:inline-flex;align-items:center;gap:7px;align-self:start}
  .verdict::before{content:"";width:9px;height:9px;border-radius:var(--r-sm);background:currentColor;flex:none}
  .verdict.refused{color:var(--red)}
  .verdict.allowed{color:var(--ink-2)}
  .what b{font-weight:600}
  .nb{white-space:nowrap}
  .why{color:var(--ink-2);font-size:14px;line-height:1.45;margin-top:4px}
  .meta{font-size:13px;color:var(--ink-3);margin-top:var(--s2);display:flex;gap:var(--s3);flex-wrap:wrap;font-variant-numeric:tabular-nums;min-width:0}
  .meta span{min-width:0;overflow-wrap:anywhere}

  .more{display:inline-block;margin-top:var(--s5,20px);padding:var(--s3) 0;
        font:600 14px/1.3 "IBM Plex Mono",monospace;color:var(--ink);text-decoration:none;
        border-bottom:2px solid var(--red);
        transition:color var(--t-fast) var(--ease)}
  @media(hover:hover){.more:hover{color:var(--red)}}
  .more:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  .receipt{font:500 13px/1 "IBM Plex Mono",monospace;letter-spacing:.04em;text-decoration:none;
    border-bottom:1px solid var(--red);padding-bottom:2px;white-space:nowrap;
    transition:color var(--t-fast) var(--ease)}
  @media(hover:hover){.receipt:hover{color:var(--red)}}
  .receipt:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  .policy{display:grid;grid-template-columns:1fr;margin-top:var(--s6)}
  @media(min-width:700px){.policy{grid-template-columns:1fr 1fr;column-gap:var(--s16)}}
  .lim{display:flex;align-items:baseline;gap:var(--s3);padding:var(--s3) 0;border-bottom:1px solid var(--rule-soft)}
  .lim .n{flex:1;font-size:14px;color:var(--ink-2)}
  .lim .v{font:600 15px/1 "IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}

  .rec.watched{background:linear-gradient(90deg, rgba(19,20,23,.045), transparent 60%);
               border-left:3px solid var(--ink-3)}
  .verdict.watched{color:var(--ink-2)}
  .verdict.watched::before{background:var(--ink-3)}
  /* An operator action is not a verdict on an order, so it does not wear a verdict's colour. */
  .rec.operator{background:none;border-left:3px solid var(--rule)}
  .verdict.operator{color:var(--ink-3)}
  .verdict.operator::before{background:var(--rule)}

  .sig{margin-top:var(--s6);padding:var(--s5);border-radius:var(--r-md);
       background:var(--paper-2);box-shadow:var(--e-1)}
  .sig-row{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--s3);
           padding:var(--s2) 0;border-bottom:1px solid var(--rule-soft)}
  .sig-row .lbl{flex:1;min-width:180px}
  .sig-row code{font:500 13px/1.5 "IBM Plex Mono",monospace;color:var(--ink-2);word-break:break-all}
  .sig-note{margin:var(--s4) 0 var(--s3);font-size:14px;line-height:1.6;color:var(--ink-2);max-width:62ch}
  .sig-cmd{display:block;padding:var(--s3) var(--s4);border-radius:var(--r-sm);
           background:var(--ink);color:var(--paper);
           font:500 13px/1.5 "IBM Plex Mono",monospace;overflow-x:auto}
  .lim .v.red{color:var(--red)}

  .install{margin:var(--s16) 0 var(--s24);padding:var(--s8);background:var(--ink);color:var(--paper);border-radius:var(--r-lg);box-shadow:var(--e-3)}
  .install h3{font-weight:800;font-size:clamp(22px,2.6vw,30px);line-height:1.05;letter-spacing:-.01em;margin-bottom:var(--s2)}
  .install p{margin:0 0 var(--s6);color:rgba(244,243,239,.62);font-size:14px;max-width:54ch}
  /* ── The sweep ──────────────────────────────────────────────────────────────────────────
     The needle is the one thing on this page that moves, and it moves once. It rests until the
     balance comes back from Solana, then travels to the position that balance implies. Nothing
     is animated for the sake of it: the motion IS the reading arriving.

     transform-box:view-box makes transform-origin resolve in the viewBox's own coordinates,
     which is what lets a CSS rotation replace the SVG rotate() attribute. Using the attribute
     and a CSS transform together does not work; they fight, and the needle vanishes. */
  .needle{transform-box:view-box; transform-origin:260px 270px;
          transform:rotate(var(--deg, 0deg));
          transition:transform var(--sweep-dur) var(--sweep-ease)}

  .install .then{margin:var(--s6) 0 0;line-height:1.75;max-width:62ch}
  .inlinecmd{display:inline-block;padding:1px 6px;border-radius:var(--r-sm);
             background:rgba(244,243,239,.10);font:500 13px/1.5 "IBM Plex Mono",monospace;
             color:var(--paper);word-break:break-all}
  .install .then a{color:var(--paper);border-bottom:1px solid rgba(244,243,239,.35);text-decoration:none;
                   transition:border-color var(--t-fast) var(--ease)}
  @media(hover:hover){.install .then a:hover{border-color:var(--red)}}
  .install .then a:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.45);border-radius:var(--r-sm)}
  .cmd{display:flex;align-items:center;gap:var(--s4);background:rgba(244,243,239,.07);border-radius:var(--r-md);padding:var(--s4);box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
  .cmd code{font:500 14px/1.4 "IBM Plex Mono",monospace;overflow-x:auto;white-space:nowrap;flex:1;min-width:0}
  .cmd button{font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;
    background:var(--red);color:var(--on-red);border:0;border-radius:var(--r-sm);padding:11px 14px;min-height:44px;cursor:pointer;
    transition:transform 80ms var(--ease), box-shadow var(--t-fast) var(--ease)}
  @media(hover:hover){.cmd button:hover{transform:translateY(-1px);box-shadow:0 6px 16px -6px rgba(224,58,47,.8)}}
  .cmd button:active{transform:scale(.97)}
  .cmd button:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.45)}

  footer a{text-decoration:none;border-bottom:1px solid var(--rule);transition:color var(--t-fast) var(--ease),border-color var(--t-fast) var(--ease)}
</style>
