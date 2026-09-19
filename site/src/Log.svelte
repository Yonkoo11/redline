<script>
  import Shell from "./lib/Shell.svelte";

  const PATH = "~/.hermes/redline/tape.jsonl";

  let rows = $state([]);
  let fileName = $state("");
  let error = $state("");
  let dragging = $state(false);
  let filters = $state([]);          // [{field, value, exclude}]

  const money = (n) => (n === null || n === undefined ? "" : `$${Number(n).toFixed(2)}`);
  const when = (ts) => new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
  const short = (s) => (s ? s.slice(0, 10) + "…" + s.slice(-6) : "");

  function verdictOf(r) {
    if (r.would_refuse) return "watched";
    return r.allowed ? "allowed" : "refused";
  }

  async function read(file) {
    error = "";
    try {
      const text = await file.text();
      const out = [];
      for (const line of text.split("\n")) {
        const t = line.trim();
        if (!t) continue;
        try { out.push(JSON.parse(t)); } catch { /* a half-written last line is normal */ }
      }
      if (out.length === 0) throw new Error("no records in that file");
      rows = out.reverse();
      fileName = file.name;
    } catch (e) {
      error = `Could not read that file: ${e.message}`;
      rows = [];
    }
  }

  function onDrop(e) {
    e.preventDefault();
    dragging = false;
    const f = e.dataTransfer?.files?.[0];
    if (f) read(f);
  }

  function addFilter(field, value, exclude) {
    if (filters.some((f) => f.field === field && f.value === value && f.exclude === exclude)) return;
    filters = [...filters, { field, value, exclude }];
  }

  const shown = $derived(
    rows.filter((r) =>
      filters.every((f) => {
        const v = f.field === "verdict" ? verdictOf(r)
                : f.field === "rule" ? (r.rule || "")
                : f.field === "market" ? (r.intent?.market || "")
                : String(r[f.field] ?? "");
        return f.exclude ? v !== f.value : v === f.value;
      })
    )
  );

  const counts = $derived.by(() => {
    const c = { allowed: 0, refused: 0, watched: 0 };
    for (const r of rows) c[verdictOf(r)]++;
    return c;
  });

  const span = $derived.by(() => {
    if (rows.length === 0) return "";
    const ts = rows.map((r) => r.ts).filter(Boolean);
    return `${when(Math.min(...ts))} to ${when(Math.max(...ts))}`;
  });

  let open = $state(new Set());
  function toggleOpen(i) {
    const n = new Set(open);
    n.has(i) ? n.delete(i) : n.add(i);
    open = n;
  }
</script>

<Shell here="log">
  <section class="head">
    <h1>Read your own log.</h1>
    <p class="lede">
      Every install writes its own record of what it judged. Open yours here. The file is parsed in
      this tab and never leaves your machine: there is no server behind this page and nothing is
      uploaded. <code>python -m redline.log</code> does the same job in a terminal, because a tool
      whose evidence can only be read through a website is a tool that asks you to trust the
      website.
    </p>
  </section>

  {#if rows.length === 0}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="drop" class:over={dragging}
         ondragover={(e) => { e.preventDefault(); dragging = true; }}
         ondragleave={() => (dragging = false)}
         ondrop={onDrop}>
      <p class="dtitle">Drop your <code>tape.jsonl</code> here</p>
      <p class="dpath">It lives at <code>{PATH}</code></p>
      <label class="pick">
        Choose the file
        <input type="file" accept=".jsonl,.json,.txt,application/json"
               onchange={(e) => e.target.files[0] && read(e.target.files[0])} />
      </label>
      {#if error}<p class="err">{error}</p>{/if}
      <p class="alt">Or in a terminal: <code>python -m redline.log</code></p>
    </div>
  {:else}
    <div class="bar">
      <div class="tallies">
        <button class="tally" onclick={() => addFilter("verdict", "refused", false)}>
          <b>{counts.refused}</b> refused
        </button>
        <button class="tally" onclick={() => addFilter("verdict", "allowed", false)}>
          <b>{counts.allowed}</b> allowed
        </button>
        {#if counts.watched}
          <button class="tally" onclick={() => addFilter("verdict", "watched", false)}>
            <b>{counts.watched}</b> watched
          </button>
        {/if}
      </div>
      <span class="lbl">{fileName} · {rows.length} records · {span}</span>
    </div>

    {#if filters.length}
      <div class="chipsRow">
        {#each filters as f, i}
          <button class="fchip" onclick={() => (filters = filters.filter((_, j) => j !== i))}>
            {f.exclude ? "not " : ""}{f.field}: {f.value || "(none)"} ×
          </button>
        {/each}
        <button class="fclear" onclick={() => (filters = [])}>clear</button>
      </div>
    {/if}

    <p class="hint">Every record is here, newest first. Nothing is sampled or trimmed. Click a value
      to narrow the list, or a row to see the record that produced it.</p>

    {#each shown as r, i}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="rec" class:refused={verdictOf(r) === "refused"} class:watched={verdictOf(r) === "watched"}>
        <button class="verdict {verdictOf(r)}" onclick={() => addFilter("verdict", verdictOf(r), false)}>
          {verdictOf(r) === "watched" ? "Watched" : r.allowed ? "Allowed" : "Refused"}
        </button>
        <div class="body" onclick={() => toggleOpen(i)}>
          <div class="what"
            >{r.intent?.kind === "perp" ? "Perpetual" : r.intent?.kind === "swap" ? "Swap" : r.intent?.kind}{#if r.intent?.market}, <button
              class="inline" onclick={(e) => { e.stopPropagation(); addFilter("market", r.intent.market, false); }}
              >{r.intent.market}</button>{/if}{#if r.intent?.notional_usd}, <span class="nb">{money(r.intent.notional_usd)} notional</span>{/if}</div>
          <div class="why">{r.reason}</div>
          <div class="meta">
            <span>{when(r.ts)}</span>
            {#if r.equity_usd}<span>equity {money(r.equity_usd)}, read {r.equity_source}</span>{/if}
            {#if r.rule}
              <button class="inline dim" onclick={(e) => { e.stopPropagation(); addFilter("rule", r.rule, false); }}>{r.rule}</button>
            {/if}
            {#if r.policy_verified === false}<span class="flag">policy unverified</span>{/if}
          </div>
          {#if open.has(i)}
            <pre class="raw">{JSON.stringify(r, null, 1)}</pre>
          {/if}
        </div>
        <div class="side">
          {#if r.memo_sig}
            <a class="receipt" href={`https://solscan.io/tx/${r.memo_sig}`}>{short(r.memo_sig)} ↗</a>
          {/if}
        </div>
      </div>
    {/each}

    {#if shown.length === 0}
      <p class="empty">Nothing matches those filters. Clear one to see records again.</p>
    {/if}

    <button class="ghost again" onclick={() => { rows = []; filters = []; fileName = ""; }}>
      Open a different file
    </button>
  {/if}
</Shell>

<style>
  .head{padding:var(--s12) 0 var(--s8);max-width:70ch}
  h1{font:800 clamp(34px,5vw,56px)/1.05 "Barlow Condensed",sans-serif;letter-spacing:-.02em;margin:0}
  .lede{margin:var(--s5,20px) 0 0;color:var(--ink-2);font-size:15px;line-height:1.7;max-width:62ch}

  .drop{padding:var(--s16) var(--s8);border-radius:var(--r-lg);text-align:center;
        background:var(--paper-2);box-shadow:var(--e-1);
        border:2px dashed var(--rule);transition:border-color var(--t) var(--ease),box-shadow var(--t) var(--ease)}
  .drop.over{border-color:var(--red);box-shadow:var(--e-2)}
  .dtitle{margin:0;font:800 clamp(20px,2.4vw,26px)/1.2 "Barlow Condensed",sans-serif}
  .dtitle code,.dpath code,.alt code{font:600 15px/1 "IBM Plex Mono",monospace}
  .dpath{margin:var(--s3) 0 0;color:var(--ink-3);font-size:14px}
  .pick{display:inline-block;margin-top:var(--s6);padding:var(--s3) var(--s5,20px);cursor:pointer;
        border-radius:var(--r-sm);background:var(--ink);color:var(--paper);box-shadow:var(--e-2);
        font:600 14px/1.3 "IBM Plex Mono",monospace}
  .pick input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
  .pick:focus-within{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35)}
  .alt{margin:var(--s6) 0 0;color:var(--ink-3);font-size:13px}
  .err{margin:var(--s4) 0 0;color:var(--red);font-size:14px}

  .bar{display:flex;align-items:baseline;gap:var(--s4);flex-wrap:wrap;
       padding-bottom:var(--s3);border-bottom:2px solid var(--ink)}
  .tallies{display:flex;gap:var(--s3);flex-wrap:wrap;margin-right:auto}
  .tally{border:none;cursor:pointer;background:transparent;color:var(--ink-2);
         font:400 14px/1 "IBM Plex Mono",monospace;padding:var(--s2) 0}
  .tally b{font-size:20px;font-weight:600;color:var(--ink);margin-right:6px;font-variant-numeric:tabular-nums}
  .tally:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  .chipsRow{display:flex;gap:var(--s2);flex-wrap:wrap;margin-top:var(--s4)}
  .fchip,.fclear{border:none;cursor:pointer;border-radius:var(--r-full);padding:var(--s2) var(--s3);
                 font:600 12px/1.3 "IBM Plex Mono",monospace;letter-spacing:.04em}
  .fchip{background:var(--ink);color:var(--paper)}
  .fclear{background:transparent;color:var(--ink-3);box-shadow:inset 0 0 0 1px var(--rule)}

  .hint{margin:var(--s5,20px) 0;font-size:13px;line-height:1.6;color:var(--ink-3);max-width:60ch}

  .rec{display:grid;grid-template-columns:120px minmax(0,1fr) auto;gap:var(--s4);align-items:start;
       padding:var(--s4) 0;border-bottom:1px solid var(--rule-soft)}
  .rec.refused{background:linear-gradient(90deg, rgba(224,58,47,.07), transparent 62%);
               border-left:3px solid var(--red);padding-left:var(--s4)}
  .rec.watched{background:linear-gradient(90deg, rgba(19,20,23,.045), transparent 60%);
               border-left:3px solid var(--ink-3);padding-left:var(--s4)}
  .verdict{border:none;background:transparent;cursor:pointer;text-align:left;padding:2px 0;
           font:600 12px/1.3 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;
           color:var(--ink-3)}
  .verdict.refused{color:var(--red)}
  .verdict.allowed{color:var(--ink-2)}
  .verdict:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  .body{cursor:pointer}
  .what{font-size:16px}
  .nb{font-variant-numeric:tabular-nums}
  .why{margin-top:2px;font-size:14px;color:var(--ink-2)}
  .meta{margin-top:var(--s2);display:flex;gap:var(--s4);flex-wrap:wrap;
        font-size:13px;color:var(--ink-3)}
  .flag{color:var(--red)}
  .inline{border:none;background:transparent;cursor:pointer;padding:0;font:inherit;color:inherit;
          font-weight:600;border-bottom:1px solid var(--rule)}
  .inline.dim{font-weight:400}
  @media(hover:hover){.inline:hover{border-color:var(--red)}}
  .inline:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  .raw{margin:var(--s3) 0 0;padding:var(--s3);border-radius:var(--r-sm);
       background:var(--ink);color:var(--paper);overflow-x:auto;
       font:400 13px/1.6 "IBM Plex Mono",monospace}

  .receipt{font:500 13px/1 "IBM Plex Mono",monospace;text-decoration:none;
           border-bottom:1px solid var(--rule);white-space:nowrap}
  @media(hover:hover){.receipt:hover{border-color:var(--red)}}

  .empty{padding:var(--s8) 0;color:var(--ink-3);font-size:14px}
  .ghost{padding:var(--s3) var(--s5,20px);border-radius:var(--r-sm);cursor:pointer;border:none;
         background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--rule);
         font:600 14px/1.3 "IBM Plex Mono",monospace}
  .again{margin-top:var(--s8)}

  @media (max-width:760px){
    .rec{grid-template-columns:1fr;gap:var(--s2)}
    .side{margin-top:var(--s2)}
  }
</style>
