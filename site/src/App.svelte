<script>
  let data = $state(null);
  let error = $state(null);

  fetch("tape.json")
    .then((r) => r.json())
    .then((d) => (data = d))
    .catch((e) => (error = String(e)));

  const explorer = (sig) => `https://solscan.io/tx/${sig}`;
  const money = (n) => (n == null ? "-" : `$${Number(n).toFixed(2)}`);
  const when = (ts) => new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
</script>

<main>
  <header>
    <img class="mark" src="mark-512.png" alt="" width="52" height="52" />
    <img class="word" src="wordmark-dark.svg" alt="redline" height="30" />
    <a class="gh" href="https://github.com/Yonkoo11/redline">source</a>
  </header>

  <section class="hero">
    <h1>Kill switch for claw traders.</h1>
    <p>
      Redline holds a ClawPump trading agent under a policy its operator wrote. An order that
      crosses the line is refused, and the refusal is written to Solana so anyone can check it.
    </p>
  </section>

  <section class="grid">
    <div class="panel">
      <h2>The policy</h2>
      {#if data?.policy}
        <dl>
          <dt>Per-trade cap</dt><dd>{data.policy.max_trade_pct_equity}% of equity</dd>
          <dt>Daily loss limit</dt><dd>{data.policy.max_daily_loss_pct}%</dd>
          <dt>Drawdown halt</dt><dd>{data.policy.max_drawdown_pct}% from the high-water mark</dd>
          <dt>Max leverage</dt><dd>{data.policy.max_leverage}&times;</dd>
          <dt>Markets</dt><dd>{data.policy.allowed_markets?.join(", ")}</dd>
          <dt>Collateral withdrawals</dt><dd>operator only</dd>
        </dl>
      {/if}
    </div>

    <div class="panel">
      <h2>The tape</h2>
      {#if error}
        <p class="mute">Tape unavailable: {error}</p>
      {:else if !data}
        <p class="mute">Reading the tape…</p>
      {:else if data.rows.length === 0}
        <p class="mute">Empty. The first entry will be a refusal, linked to Solscan.</p>
      {:else}
        <ul class="tape">
          {#each [...data.rows].reverse() as r}
            <li class:refused={!r.allowed}>
              <span class="verdict">{r.allowed ? "allowed" : "refused"}</span>
              <span class="what">
                {r.intent?.kind}
                {#if r.intent?.market}&middot; {r.intent.market}{/if}
                {#if r.intent?.notional_usd}&middot; {money(r.intent.notional_usd)}{/if}
              </span>
              <span class="why">{r.reason}</span>
              <span class="meta">
                {when(r.ts)}
                {#if r.memo_sig}&middot; <a href={explorer(r.memo_sig)} rel="noreferrer">on Solana</a>{/if}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </section>

  <footer>
    <a href="https://x.com/useredline">@useredline</a>
    <span>The AnsemHack Clawrena &middot; Solana</span>
  </footer>
</main>

<style>
  main { max-width: 980px; margin: 0 auto; padding: 28px 16px 64px; }
  header { display: flex; align-items: center; gap: 13px; }
  .mark { border-radius: 50%; }
  .gh { margin-left: auto; color: var(--mute); text-decoration: none; font-size: 14px; }
  .gh:hover { color: var(--ink); }
  .hero { margin: 44px 0 30px; }
  h1 { font-size: clamp(30px, 6vw, 54px); line-height: 1.02; margin: 0 0 14px; letter-spacing: -0.015em; }
  .hero p { max-width: 58ch; color: var(--mute); font-size: 17px; line-height: 1.5; margin: 0; }
  .grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
  @media (min-width: 760px) { .grid { grid-template-columns: 300px 1fr; align-items: start; } }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px;
           box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset, 0 12px 28px -22px #000; }
  h2 { margin: 0 0 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.09em; color: var(--mute); }
  dl { display: grid; grid-template-columns: 1fr auto; gap: 7px 14px; margin: 0; font-size: 14px; }
  dt { color: var(--mute); } dd { margin: 0; text-align: right; }
  .mute { color: var(--mute); margin: 0; font-size: 14px; }
  .tape { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
  .tape li { display: grid; grid-template-columns: auto 1fr; gap: 3px 12px; padding: 11px 0 12px;
             border-top: 1px solid var(--line); font-size: 14px; }
  .tape li:first-child { border-top: 0; padding-top: 0; }
  .verdict { grid-row: 1; font-weight: 600; color: #7fd18c; }
  .refused .verdict { color: var(--red); }
  .what { grid-row: 1; }
  .why { grid-column: 2; color: var(--ink); opacity: 0.85; }
  .meta { grid-column: 2; color: var(--mute); font-size: 13px; }
  .meta a { color: var(--mute); }
  .meta a:hover { color: var(--ink); }
  footer { margin-top: 44px; display: flex; gap: 14px; color: var(--mute); font-size: 14px; }
</style>
