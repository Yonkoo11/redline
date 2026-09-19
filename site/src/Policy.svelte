<script>
  import Shell from "./lib/Shell.svelte";

  const DEST = "~/.hermes/redline/policy.json";
  const TODAY = new Date().toISOString().slice(0, 10);

  // Each preset says who it is for and what it costs. Exactly one is recommended for most people.
  const PRESETS = [
    {
      key: "watching",
      name: "Watching",
      note: "For limits you have never run. Judges every order and stops none, so you can read a day of verdicts before anything is enforced. Start here.",
      v: { mode: "shadow", max_trade_pct_equity: 10, max_daily_loss_pct: 5, max_drawdown_pct: 15,
           max_leverage: 2, equity_floor_usd: 5, refusal_cooldown_count: 5, refusal_cooldown_minutes: 30 },
    },
    {
      key: "guard",
      name: "Standing guard",
      note: "For an agent that runs while you are asleep. Recommended once watching has shown you nothing surprising.",
      v: { mode: "enforce", max_trade_pct_equity: 10, max_daily_loss_pct: 5, max_drawdown_pct: 15,
           max_leverage: 2, equity_floor_usd: 5, refusal_cooldown_count: 5, refusal_cooldown_minutes: 30 },
    },
    {
      key: "desk",
      name: "At the keyboard",
      note: "Wider limits for an agent you are actively supervising, and only while you are. Leaving this running unattended is how an account is emptied.",
      v: { mode: "enforce", max_trade_pct_equity: 25, max_daily_loss_pct: 10, max_drawdown_pct: 25,
           max_leverage: 3, equity_floor_usd: 5, refusal_cooldown_count: 8, refusal_cooldown_minutes: 15 },
    },
  ];

  const MARKETS = ["SOL", "ETH", "BTC"];
  const TOKENS = ["SOL", "USDC", "USDT", "JUP", "JTO", "BONK"];

  let preset = $state("watching");
  let p = $state({ ...PRESETS[0].v });
  let markets = $state(["SOL", "ETH"]);
  let tokens = $state(["SOL", "USDC"]);
  let destinations = $state("");
  let copied = $state(false);

  function apply(k) {
    preset = k;
    p = { ...PRESETS.find((x) => x.key === k).v };
  }

  const NUM = {
    max_trade_pct_equity: { label: "Per-order cap", unit: "% of equity", min: 0.1, max: 100,
      help: "The largest single order, as a share of what the wallet is worth right now." },
    max_daily_loss_pct: { label: "Daily loss limit", unit: "%", min: 0.1, max: 100,
      help: "Stops opening trades once the day is down this much. The day starts at 00:00 UTC and the clock resets then." },
    max_drawdown_pct: { label: "Drawdown halt", unit: "%", min: 0.1, max: 100,
      help: "A hard stop, measured from the highest equity ever seen. Once it fires, nothing trades until you clear it." },
    max_leverage: { label: "Maximum leverage", unit: "×", min: 1, max: 25,
      help: "Refuses any order asking for more than this." },
    equity_floor_usd: { label: "Equity floor", unit: "USD", min: 0, max: 1e9,
      help: "Below this the agent stops trading entirely, so a small account cannot be ground to dust in fees." },
    refusal_cooldown_count: { label: "Refusals before cooling down", unit: "refusals", min: 1, max: 100,
      help: "An agent that keeps hitting the wall is confused. After this many refusals it is paused." },
    refusal_cooldown_minutes: { label: "Cool-down length", unit: "minutes", min: 1, max: 1440,
      help: "How long the pause lasts. It then resumes on its own, with the same limits." },
  };

  // Field-level problems sit at the field. Cross-field problems sit at the top.
  const fieldErrors = $derived.by(() => {
    const out = {};
    for (const [k, m] of Object.entries(NUM)) {
      const v = Number(p[k]);
      if (!Number.isFinite(v)) out[k] = "Needs a number.";
      else if (v < m.min) out[k] = `Must be at least ${m.min}${m.unit === "%" ? "%" : ""}.`;
      else if (v > m.max) out[k] = `Must be ${m.max}${m.unit === "%" ? "%" : ""} or less.`;
    }
    return out;
  });

  const crossErrors = $derived.by(() => {
    const out = [];
    if (Number(p.max_drawdown_pct) <= Number(p.max_daily_loss_pct))
      out.push(`The drawdown halt (${p.max_drawdown_pct}%) is not above the daily loss limit (${p.max_daily_loss_pct}%), so the daily limit always stops trading first and the halt can never fire.`);
    const exposure = Number(p.max_trade_pct_equity) * Number(p.max_leverage);
    if (exposure > 100)
      out.push(`A single order may be ${p.max_trade_pct_equity}% of equity at ${p.max_leverage}× leverage, which is ${Math.round(exposure)}% of the account in one position. Lower the cap or the leverage.`);
    if (markets.length === 0)
      out.push("No markets are allowed, so every perpetual order will be refused.");
    if (tokens.length === 0)
      out.push("No tokens are allowed, so every swap will be refused.");
    return out;
  });

  const ready = $derived(Object.keys(fieldErrors).length === 0);

  const policyFile = $derived.by(() => ({
    schema: 1,
    generated: TODAY,
    mode: p.mode,
    max_trade_pct_equity: Number(p.max_trade_pct_equity),
    max_daily_loss_pct: Number(p.max_daily_loss_pct),
    max_drawdown_pct: Number(p.max_drawdown_pct),
    max_leverage: Number(p.max_leverage),
    equity_floor_usd: Number(p.equity_floor_usd),
    allowed_markets: markets,
    allowed_tokens: tokens,
    allowed_destinations: destinations.split(/[\s,]+/).filter(Boolean),
    refusal_cooldown_count: Number(p.refusal_cooldown_count),
    refusal_cooldown_minutes: Number(p.refusal_cooldown_minutes),
  }));

  const text = $derived(JSON.stringify(policyFile, null, 1) + "\n");

  function toggle(list, v) {
    return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
  }

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "policy.json" });
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copy() {
    await navigator.clipboard.writeText(text);
    copied = true;
    setTimeout(() => (copied = false), 1600);
  }
</script>

<Shell here="policy">
  <section class="head">
    <h1>Set the limits once,<br />then let it trade.</h1>
    <p class="lede">
      These are the numbers Redline enforces on every order your agent sends. Choose a starting
      point, change what you need, then sign the file with a key the agent does not hold. Nothing
      here is sent anywhere. The file is built in your browser.
    </p>
  </section>

  <div class="presets">
    {#each PRESETS as x}
      <button class="preset" class:on={preset === x.key} onclick={() => apply(x.key)}>
        <span class="pname">{x.name}</span>
        <span class="pnote">{x.note}</span>
      </button>
    {/each}
  </div>

  {#if crossErrors.length}
    <div class="warn" role="status">
      <span class="wtitle">Worth a second look</span>
      <ul>{#each crossErrors as e}<li>{e}</li>{/each}</ul>
    </div>
  {/if}

  <div class="split">
    <div class="form">
      <div class="modeRow">
        <span class="n">What it does when an order fails</span>
        <div class="seg">
          <button class:on={p.mode === "shadow"} onclick={() => (p.mode = "shadow")}>Watch only</button>
          <button class:on={p.mode === "enforce"} onclick={() => (p.mode = "enforce")}>Refuse it</button>
        </div>
      </div>
      <p class="modeNote">
        {p.mode === "shadow"
          ? "Every order is judged and written down, and none are stopped. Read the log, then come back and switch this to refusing."
          : "A failing order is stopped before it reaches the venue, and the refusal is written to Solana."}
      </p>

      {#each Object.entries(NUM) as [k, m]}
        <div class="field" class:bad={fieldErrors[k]}>
          <label for={k}>{m.label}</label>
          <div class="inputRow">
            <input id={k} type="number" inputmode="decimal" bind:value={p[k]}
                   min={m.min} max={m.max} step={m.unit === "%" || m.unit === "×" ? 0.5 : 1} />
            <span class="unit">{m.unit}</span>
          </div>
          <p class="help">{fieldErrors[k] ?? m.help}</p>
        </div>
      {/each}

      <div class="field">
        <span class="lbl2">Markets it may trade</span>
        <div class="chips">
          {#each MARKETS as m}
            <button class="chip" class:on={markets.includes(m)}
                    onclick={() => (markets = toggle(markets, m))}>{m}</button>
          {/each}
        </div>
        <p class="help">Anything not selected is refused, whatever the size.</p>
      </div>

      <div class="field">
        <span class="lbl2">Tokens it may swap</span>
        <div class="chips">
          {#each TOKENS as t}
            <button class="chip" class:on={tokens.includes(t)}
                    onclick={() => (tokens = toggle(tokens, t))}>{t}</button>
          {/each}
        </div>
        <p class="help">A token Redline cannot price is refused, so an unknown token is never traded by accident.</p>
      </div>

      <div class="field">
        <label for="dest">Addresses it may send funds to</label>
        <textarea id="dest" rows="3" bind:value={destinations}
                  placeholder="one Solana address per line, or leave empty"></textarea>
        <p class="help">Empty means no transfers at all, which is the right answer for most agents.</p>
      </div>
    </div>

    <div class="preview">
      <div class="pvhead">
        <span class="lbl">This file goes at</span>
        <code>{DEST}</code>
      </div>
      <pre class="file">{text}</pre>

      <div class="actions">
        <button class="primary" onclick={download} disabled={!ready}>Download policy.json</button>
        <button class="ghost" onclick={copy} disabled={!ready}>{copied ? "Copied" : "Copy"}</button>
      </div>

      <ol class="next">
        <li>
          Save it to <code>{DEST}</code>, or paste it there.
        </li>
        <li>
          Make the key that signs it, once ever. The command ships inside the plugin, at
          <code>~/.hermes/plugins/redline/redline</code>:
          <code class="cmd">redline sign keygen</code>
          Keep that file somewhere your agent cannot read, and back it up.
        </li>
        <li>
          Sign these limits:
          <code class="cmd">redline sign sign {DEST}</code>
        </li>
        <li>
          Pin the public half in your shell, using the key the last step printed:
          <code class="cmd">export REDLINE_OPERATOR_PUBKEY="..."</code>
        </li>
      </ol>
      <p class="tail">
        Until a policy verifies against that pinned key, Redline refuses every order rather than
        falling back to a default. That is deliberate.
      </p>
    </div>
  </div>
</Shell>

<style>
  .head{padding:var(--s12) 0 var(--s8);max-width:70ch}
  h1{font:800 clamp(34px,5vw,56px)/1.05 "Barlow Condensed",sans-serif;letter-spacing:-.02em;margin:0}
  .lede{margin:var(--s5,20px) 0 0;color:var(--ink-2);font-size:15px;line-height:1.7;max-width:62ch}

  .presets{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--s4);margin-bottom:var(--s8)}
  .preset{display:flex;flex-direction:column;gap:var(--s2);text-align:left;cursor:pointer;
          padding:var(--s5,20px);border:none;border-radius:var(--r-md);background:var(--paper-2);
          box-shadow:var(--e-1);transition:box-shadow var(--t) var(--ease),transform var(--t) var(--ease)}
  @media(hover:hover){.preset:hover{box-shadow:var(--e-2);transform:translateY(-2px)}}
  .preset:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35)}
  .preset.on{background:var(--ink);box-shadow:var(--e-2)}
  .pname{font:800 19px/1.1 "Barlow Condensed",sans-serif;letter-spacing:.01em}
  .preset.on .pname{color:var(--paper)}
  .pnote{font-size:13px;line-height:1.6;color:var(--ink-2)}
  .preset.on .pnote{color:rgba(244,243,239,.66)}

  .warn{margin-bottom:var(--s6);padding:var(--s5,20px);border-radius:var(--r-md);
        background:rgba(224,58,47,.07);border-left:3px solid var(--red)}
  .wtitle{display:block;font:600 13px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;
          text-transform:uppercase;color:var(--red);margin-bottom:var(--s3)}
  .warn ul{margin:0;padding-left:1.1em;color:var(--ink-2);font-size:14px;line-height:1.65}
  .warn li + li{margin-top:var(--s2)}

  .split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s8);align-items:start}

  .field{padding:var(--s4) 0;border-bottom:1px solid var(--rule-soft)}
  label,.lbl2{display:block;font-size:14px;color:var(--ink);margin-bottom:var(--s2)}
  .inputRow{display:flex;align-items:baseline;gap:var(--s3)}
  .inputRow input{flex:0 0 190px;width:190px}
  input[type="number"],textarea{
    min-width:0;padding:var(--s3);border:1px solid var(--rule);border-radius:var(--r-sm);
    background:var(--paper-2);color:var(--ink);font:600 16px/1.3 "IBM Plex Mono",monospace;
    font-variant-numeric:tabular-nums;box-shadow:var(--e-1);
    transition:border-color var(--t-fast) var(--ease),box-shadow var(--t-fast) var(--ease)}
  textarea{width:100%;font-weight:400;font-size:14px;line-height:1.6;resize:vertical}
  input:focus-visible,textarea:focus-visible{outline:none;border-color:var(--ink);
    box-shadow:0 0 0 3px rgba(224,58,47,.25)}
  .unit{font-size:13px;color:var(--ink-3);white-space:nowrap}
  .help{margin:var(--s2) 0 0;font-size:13px;line-height:1.6;color:var(--ink-3);max-width:52ch}
  .field.bad input{border-color:var(--red)}
  .field.bad .help{color:var(--red)}

  .modeRow{display:flex;align-items:center;gap:var(--s4);flex-wrap:wrap;padding-bottom:var(--s3)}
  .modeRow .n{flex:1;font-size:14px}
  .seg{display:flex;border-radius:var(--r-sm);overflow:hidden;box-shadow:var(--e-1)}
  .seg button{padding:var(--s2) var(--s4);border:none;cursor:pointer;background:var(--paper-2);
              color:var(--ink-2);font:600 13px/1.4 "IBM Plex Mono",monospace;
              transition:background var(--t-fast) var(--ease),color var(--t-fast) var(--ease)}
  .seg button.on{background:var(--ink);color:var(--paper)}
  .seg button:focus-visible{outline:none;box-shadow:inset 0 0 0 2px var(--red)}
  .modeNote{margin:0 0 var(--s4);font-size:13px;line-height:1.6;color:var(--ink-3);max-width:54ch}

  .chips{display:flex;flex-wrap:wrap;gap:var(--s2)}
  .chip{padding:var(--s2) var(--s4);border:none;border-radius:var(--r-full);cursor:pointer;
        background:var(--paper-2);color:var(--ink-3);box-shadow:var(--e-1);
        font:600 13px/1.4 "IBM Plex Mono",monospace;
        transition:background var(--t-fast) var(--ease),color var(--t-fast) var(--ease)}
  .chip.on{background:var(--ink);color:var(--paper)}
  .chip:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35)}

  .preview{position:sticky;top:var(--s6);padding:var(--s6);border-radius:var(--r-lg);
           background:var(--paper-2);box-shadow:var(--e-2)}
  .pvhead{display:flex;align-items:baseline;gap:var(--s3);flex-wrap:wrap;margin-bottom:var(--s3)}
  .pvhead code{font:600 13px/1 "IBM Plex Mono",monospace;color:var(--ink)}
  .file{margin:0;padding:var(--s4);border-radius:var(--r-md);background:var(--ink);color:var(--paper);
        font:400 13px/1.6 "IBM Plex Mono",monospace;overflow-x:auto;max-height:46vh;overflow-y:auto}

  .actions{display:flex;gap:var(--s3);margin-top:var(--s5,20px);flex-wrap:wrap}
  .primary,.ghost{padding:var(--s3) var(--s5,20px);border-radius:var(--r-sm);cursor:pointer;border:none;
                  font:600 14px/1.3 "IBM Plex Mono",monospace;
                  transition:transform var(--t-fast) var(--ease),box-shadow var(--t-fast) var(--ease)}
  .primary{background:var(--red);color:var(--on-red);box-shadow:var(--e-2)}
  .ghost{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--rule)}
  .primary:active,.ghost:active{transform:scale(.97)}
  .primary:disabled,.ghost:disabled{opacity:.45;cursor:not-allowed}
  .primary:focus-visible,.ghost:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35)}

  .next{margin:var(--s6) 0 0;padding-left:1.2em;color:var(--ink-2);font-size:14px;line-height:1.7}
  .next li + li{margin-top:var(--s3)}
  .next code{font:600 13px/1.5 "IBM Plex Mono",monospace}
  .next code.cmd{display:block;margin:var(--s2) 0;padding:var(--s2) var(--s3);border-radius:var(--r-sm);
                 background:var(--ink);color:var(--paper);font-weight:500;overflow-x:auto}
  .tail{margin:var(--s5,20px) 0 0;font-size:13px;line-height:1.65;color:var(--ink-3);max-width:54ch}

  @media (max-width:900px){
    .presets{grid-template-columns:1fr}
    .split{grid-template-columns:1fr;gap:var(--s6)}
    .preview{position:static}
  }
</style>
