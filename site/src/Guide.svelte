<script>
  import Shell from "./lib/Shell.svelte";

  // Written for the moment an operator needs it: something was just refused and they do not know
  // why. Every entry ends with what to do, not with what happened.
  const REFUSALS = [
    {
      rule: "trade_cap",
      says: "notional $X > cap $Y",
      means: "The order was larger than your per-order cap allows, measured against the wallet's value at that moment.",
      does: "Nothing reached the venue. The refusal was written to Solana.",
      do: "If the agent keeps asking for this size, its own sizing is wrong, not yours. Fix the agent. If you genuinely want larger orders, raise the cap on the policy page, re-sign, and note that one order can now spend more of the day's loss budget.",
    },
    {
      rule: "equity",
      says: "equity unreadable; refusing (fail closed)",
      means: "The balance could not be read, so no cap expressed as a share of equity could be checked.",
      does: "Everything is refused until the balance can be read again.",
      do: "Usually the Solana endpoint or the price source is down. It recovers on its own. This is the intended behaviour: guessing a balance during an outage is how accounts empty.",
    },
    {
      rule: "price",
      says: "could not price the order; refusing (fail closed)",
      means: "The order named a token Redline cannot value, so no size limit could be applied to it.",
      does: "Refused, and no receipt is written for the attempt beyond the log line.",
      do: "Either the token is not one you allowed, or it is one Redline has no decimals for. Add it to the allowed list only if you can price it.",
    },
    {
      rule: "unsigned_policy",
      says: "policy not verified",
      means: "The limits file is missing, unsigned, altered since it was signed, or the operator key is not pinned in this shell.",
      does: "Every order is refused. There is no fallback to defaults, on purpose.",
      do: "Run the check command below. If it says the policy was altered, something changed your limits without your key. Look at the file before you re-sign it.",
    },
    {
      rule: "drawdown",
      says: "drawdown X% >= Y%",
      means: "Equity fell that far below the highest value ever recorded. This is a latch, not a threshold.",
      does: "Everything is halted and stays halted, including after a restart.",
      do: "This is the limit that exists for the worst day, so read the log before you touch it. Clearing is a deliberate act with its own command, and it writes a record like everything else. It also resets the high-water mark to where you are now, because otherwise the next order re-halts against the old mark.",
    },
    {
      rule: "daily_loss",
      says: "daily loss X% >= Y%",
      means: "The day is down more than the daily limit allows. The day starts at 00:00 UTC.",
      does: "New trades are refused. Existing positions are untouched, because Redline never acts on its own.",
      do: "First check whether the fall was money you spent rather than money the agent lost. The limit compares equity now against equity at the start of the day, and it cannot see why equity moved, so a fee you paid, a transfer out or a withdrawal looks identical to a trading loss. Run the day command below. If it was an outflow, say so and the day rebaselines. Otherwise wait for the UTC day to roll.",
    },
    {
      rule: "spend_cap",
      says: "payment $X > spend limit $Y",
      means: "Something asked to pay out rather than trade: an inference call, a pod top-up, a token launch, or collateral moved into an account Redline cannot read.",
      does: "Refused before the payment left.",
      do: "These tools take any amount and send it anywhere, which is why their limit is separate from the trading cap and small by default. Raise it deliberately, and only as far as you would be comfortable losing in one call.",
    },
    {
      rule: "spend_unpriced",
      says: "payment of an unreadable amount",
      means: "A payment tool was called without naming an amount Redline could read, so no limit could be applied to it.",
      does: "Refused.",
      do: "This is the fail-closed path for payment tools, including ones the platform ships after this was written. If it is a tool you trust and use often, tell me and it can be priced properly rather than refused.",
    },
    {
      rule: "daily_turnover",
      says: "today's turnover plus this order exceeds the budget",
      means: "Every order today has been inside the per-order cap, and together they have cycled the account more times than the budget allows.",
      does: "New orders are refused until the UTC day rolls.",
      do: "This usually means the agent is in a loop. Nothing here is necessarily losing money, but each pass pays a fee, and fees are how a small account bleeds out without any single order looking wrong. Read the log before raising the budget.",
    },
    {
      rule: "internal_error",
      says: "Redline could not make a decision, so it made the safe one",
      means: "Something inside Redline failed: a damaged state or policy file, an unreadable directory, a bug.",
      does: "Refused. This matters because the runtime lets a tool call through when a hook raises, so failing loudly and refusing is the only safe answer.",
      do: "The message names the error. A damaged state file is the common case, and deleting it starts a fresh one, which also clears any halt, so read the log first.",
    },
    {
      rule: "bad_notional",
      says: "notional is not a usable number",
      means: "The order's size came out as not-a-number, infinite, or negative.",
      does: "Refused.",
      do: "Nothing to fix on your side. These values compare false against every limit, so they would otherwise pass every check and be reported as within policy.",
    },
    {
      rule: "cooldown",
      says: "too many refusals recently; cooling down",
      means: "The agent hit the wall repeatedly in a short window, which usually means it is confused rather than unlucky.",
      does: "Paused for the cool-down length, then resumes with the same limits.",
      do: "Read the last few refusals in your log. They are nearly always the same rule repeating, which points at the agent's sizing or its market list.",
    },
    {
      rule: "withdraw",
      says: "collateral withdrawals are operator-only",
      means: "Something asked to move collateral out.",
      does: "Always refused, with no setting to change it.",
      do: "Move collateral yourself. This is not configurable by design.",
    },
    {
      rule: "destination",
      says: "destination ... not on the allowlist",
      means: "A transfer was attempted to an address you did not list.",
      does: "Refused. An empty allowlist means no transfers at all.",
      do: "If the address is genuinely yours, add it on the policy page and re-sign. If it is not, you have just watched the guardrail do the thing you installed it for.",
    },
  ];
</script>

<Shell here="guide">
  <section class="head">
    <h1>When something<br />gets refused.</h1>
    <p class="lede">
      Redline refuses rather than guesses. That is the whole design, and it means you will
      occasionally see a refusal you did not expect. Every reason it can give is listed here, with
      what it means and what to do next.
    </p>
  </section>

  <section class="band">
    <h2>Start here, in order</h2>
    <ol class="steps">
      <li>
        <b>Install it.</b>
        <code class="cmd">hermes plugins install Yonkoo11/redline && hermes plugins enable redline</code>
        The commands below live inside the plugin. Put them on your path once and they work from
        anywhere:
        <code class="cmd">export PATH="$HOME/.hermes/plugins/redline:$PATH"</code>
      </li>
      <li>
        <b>Make your key, once ever.</b> Keep the file somewhere the agent cannot read, and back it up.
        <code class="cmd">redline sign keygen</code>
      </li>
      <li>
        <b>Build your limits</b> on the <a href="../policy/">policy page</a>, save the file to
        <code>~/.hermes/redline/policy.json</code>, then sign it.
        <code class="cmd">redline sign sign ~/.hermes/redline/policy.json</code>
      </li>
      <li>
        <b>Pin the public half</b> in your shell, using the key the last step printed.
        <code class="cmd">export REDLINE_OPERATOR_PUBKEY="..."</code>
      </li>
      <li>
        <b>Watch before you enforce.</b> Run a session with nothing blocked, read what would have
        been stopped, then switch the policy to refusing.
        <code class="cmd">export REDLINE_MODE=shadow</code>
      </li>
    </ol>
  </section>

  <section>
    <div class="section-head">
      <h2>Every reason it can refuse</h2>
      <span class="lbl">every rule, in the order they are checked</span>
    </div>

    {#each REFUSALS as r}
      <article class="entry">
        <div class="rleft">
          <code class="rule">{r.rule}</code>
          <span class="says">{r.says}</span>
        </div>
        <div class="rbody">
          <p class="means">{r.means}</p>
          <p class="does"><span class="k">What happened</span>{r.does}</p>
          <p class="do"><span class="k">What to do</span>{r.do}</p>
        </div>
      </article>
    {/each}
  </section>

  <section class="band">
    <h2>Checks you can run</h2>
    <dl class="checks">
      <dt>Are my limits the ones I signed?</dt>
      <dd><code class="cmd">redline sign check ~/.hermes/redline/policy.json</code></dd>
      <dt>What has it decided so far?</dt>
      <dd><code class="cmd">redline log --refused</code>
        <span>Filters, tallies and raw records, all in the terminal. Or open the file on the
        <a href="../log/">log page</a>, which reads it in your browser. The file on your machine is
        the truth either way, and the site is only a nicer lens on it.</span></dd>
      <dt>Why is the day down, and was it a loss or a spend?</dt>
      <dd><code class="cmd">redline day</code>
        <span>If the fall was money you moved, <code>redline day reset</code> moves the
        day's starting point down to where you are now. It is written to your log like any other
        decision, it can only forgive a fall that already happened, and it never touches the
        drawdown high-water mark.</span></dd>
      <dt>It halted on drawdown. Now what?</dt>
      <dd><code class="cmd">redline halt</code>
        <span>Shows why, and what clearing would do. <code>redline halt clear</code>
        clears it and writes that decision to your log.</span></dd>
      <dt>Is the plugin actually loaded?</dt>
      <dd><code class="cmd">hermes plugins validate</code></dd>
    </dl>
  </section>

  <section class="band dark">
    <h2>What it does not do</h2>
    <ul class="nots">
      <li><b>It never trades.</b> It only ever refuses. Nothing in Redline opens, closes or sizes a position.</li>
      <li><b>It never holds a key to your wallet.</b> It reads a balance and judges a call.</li>
      <li><b>It cannot stop an operator who keeps the signing key where the agent can read it.</b> Signing raises the bar from editing a file to stealing a key. Keep the key elsewhere.</li>
      <li><b>It does not watch positions between calls.</b> It acts at the moment a tool is called, not continuously.</li>
      <li><b>It counts every token in the wallet, and refuses if it cannot price one of them.</b> Skipping an unpriceable holding would under-count, and money the reader cannot see looks exactly like money that was lost. Phoenix collateral is still outside the reading.</li>
      <li><b>It cannot tell a spend from a loss.</b> The daily limit reads equity, so a fee you paid or a transfer you made counts against the day. That is why the rebaseline command exists, and why it writes a record when you use it.</li>
    </ul>
  </section>
</Shell>

<style>
  .head{padding:var(--s12) 0 var(--s8);max-width:70ch}
  h1{font:800 clamp(34px,5vw,56px)/1.05 "Barlow Condensed",sans-serif;letter-spacing:-.02em;margin:0}
  h2{font:800 clamp(22px,2.6vw,30px)/1.1 "Barlow Condensed",sans-serif;letter-spacing:-.01em;margin:0}
  .lede{margin:var(--s5,20px) 0 0;color:var(--ink-2);font-size:15px;line-height:1.7;max-width:62ch}

  .band{margin:var(--s12) 0;padding:var(--s8);border-radius:var(--r-lg);
        background:var(--paper-2);box-shadow:var(--e-1)}
  .band.dark{background:var(--ink);color:var(--paper);box-shadow:var(--e-3)}

  .section-head{display:flex;align-items:baseline;gap:var(--s4);flex-wrap:wrap;
                margin:var(--s16) 0 var(--s6);padding-bottom:var(--s3);border-bottom:2px solid var(--ink)}
  .section-head .lbl{margin-left:auto}

  .steps{margin:var(--s6) 0 0;padding-left:1.3em;color:var(--ink-2);font-size:15px;line-height:1.7}
  .steps li + li{margin-top:var(--s5,20px)}
  .steps b{color:var(--ink)}
  code{font:600 13px/1.5 "IBM Plex Mono",monospace}
  .cmd{display:block;margin:var(--s2) 0 0;padding:var(--s3) var(--s4);border-radius:var(--r-sm);
       background:var(--ink);color:var(--paper);font-weight:500;overflow-x:auto}

  .entry{display:grid;grid-template-columns:230px minmax(0,1fr);gap:var(--s6);
         padding:var(--s6) 0;border-bottom:1px solid var(--rule-soft)}
  .rleft{display:flex;flex-direction:column;gap:var(--s2)}
  .rule{align-self:start;padding:var(--s1,4px) var(--s2);border-radius:var(--r-sm);
        background:var(--red);color:var(--on-red);font-weight:600}
  .says{font:400 13px/1.5 "IBM Plex Mono",monospace;color:var(--ink-3)}
  .rbody p{margin:0 0 var(--s3);font-size:15px;line-height:1.7;color:var(--ink-2);max-width:66ch}
  .rbody .means{color:var(--ink)}
  .k{display:block;font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;
     text-transform:uppercase;color:var(--ink-3);margin-bottom:var(--s1,4px)}

  .checks{margin:var(--s6) 0 0}
  .checks dt{font-size:15px;color:var(--ink);margin-top:var(--s5,20px)}
  .checks dd{margin:var(--s2) 0 0}
  .checks dd span{display:block;margin-top:var(--s2);font-size:13px;color:var(--ink-3)}

  .nots{margin:var(--s6) 0 0;padding-left:1.1em;font-size:15px;line-height:1.75;
        color:rgba(244,243,239,.72);max-width:68ch}
  .nots li + li{margin-top:var(--s3)}
  .nots b{color:var(--paper)}

  a{color:inherit}

  @media (max-width:760px){
    .entry{grid-template-columns:1fr;gap:var(--s3)}
    .band{padding:var(--s6)}
  }
</style>
