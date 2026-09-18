<script>
  // Shell only. Real entries arrive from tape.jsonl once the Phase 1 gate passes.
  const tape = [];
  const policy = { max_trade_pct_equity: 10, max_daily_loss_pct: 5, max_drawdown_pct: 15, max_leverage: 2, allowed_markets: ["SOL", "ETH"] };
</script>

<main>
  <header>
    <img class="mark" src="mark-512.png" alt="" width="56" height="56" />
    <img class="word" src="wordmark-dark.svg" alt="redline" height="34" />
  </header>

  <section class="hero">
    <h1>Kill switch for claw traders.</h1>
    <p>Redline holds a ClawPump trading agent under a policy its operator signed. An order that crosses the line is refused, and the refusal is posted on Solana.</p>
    <p class="status">Status: policy engine built and tested on a fixture venue. No mainnet transaction yet. The tape below fills the moment one exists.</p>
  </section>

  <section class="grid">
    <div class="panel">
      <h2>Policy</h2>
      <dl>
        <dt>Per-trade cap</dt><dd>{policy.max_trade_pct_equity}% of equity</dd>
        <dt>Daily loss limit</dt><dd>{policy.max_daily_loss_pct}%</dd>
        <dt>Drawdown halt</dt><dd>{policy.max_drawdown_pct}% from high-water mark</dd>
        <dt>Max leverage</dt><dd>{policy.max_leverage}×</dd>
        <dt>Markets</dt><dd>{policy.allowed_markets.join(", ")}</dd>
      </dl>
    </div>
    <div class="panel">
      <h2>Tape</h2>
      {#if tape.length === 0}
        <p class="empty">Empty. The first entry will be a refusal on Solana mainnet, linked to Solscan.</p>
      {/if}
    </div>
  </section>

  <footer>
    <a href="https://x.com/useredline">@useredline</a>
    <span>·</span>
    <span>The AnsemHack Clawrena · Solana</span>
  </footer>
</main>

<style>
  main{max-width:960px;margin:0 auto;padding:32px 16px 64px}
  header{display:flex;align-items:center;gap:14px}
  .mark{border-radius:50%}
  .hero{margin:48px 0 32px}
  h1{font-size:clamp(32px,6vw,56px);line-height:1;margin:0 0 16px;letter-spacing:-0.01em}
  .hero p{max-width:60ch;color:var(--mute);font-size:18px;line-height:1.45;margin:0 0 12px}
  .status{color:var(--ink);border-left:3px solid var(--red);padding-left:12px}
  .grid{display:grid;grid-template-columns:1fr;gap:16px}
  @media(min-width:720px){.grid{grid-template-columns:1fr 1fr}}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;box-shadow:0 1px 0 #000 inset,0 8px 24px -16px #000}
  h2{margin:0 0 12px;font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute)}
  dl{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin:0}dt{color:var(--mute)}dd{margin:0}
  .empty{color:var(--mute);margin:0}
  footer{margin-top:48px;display:flex;gap:10px;color:var(--mute);font-size:14px}
</style>
