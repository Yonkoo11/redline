<script>
  // The frame every page shares: mark, nav, footer. The home page keeps its own hero, so this
  // carries only what must look identical on all four routes.
  let { here = "", children } = $props();

  const ROUTES = [
    { href: "./",        key: "home",   label: "Redline" },
    { href: "./policy/", key: "policy", label: "Policy" },
    { href: "./log/",    key: "log",    label: "Log" },
    { href: "./guide/",  key: "guide",  label: "Guide" },
  ];

  // Pages sit one directory deep, so their links back out need a level.
  const prefix = here === "home" ? "" : "../";
</script>

<div class="wrap">
  <header class="masthead">
    <a class="brand" href={prefix || "./"} aria-label="Redline home">
      <svg class="brandmark" viewBox="0 0 512 512" aria-hidden="true">
        <circle cx="256" cy="256" r="248" fill="#131417" />
        <path d="M 116 256 A 140 140 0 0 1 366 170" fill="none" stroke="#3A3C42" stroke-width="26" />
        <path d="M 366 170 A 140 140 0 0 1 396 256" fill="none" stroke="#E03A2F" stroke-width="26" />
        <circle cx="256" cy="256" r="26" fill="#F4F3EF" />
        <path d="M240 240 L272 240 L336 150 L312 140 Z" fill="#F4F3EF" />
      </svg>
      <span class="brandword">redline</span>
    </a>
    <nav>
      {#each ROUTES.slice(1) as r}
        <a href={prefix + r.href.replace("./", "")} class:on={here === r.key}>{r.label}</a>
      {/each}
    </nav>
  </header>

  {@render children()}

  <footer>
    <a href="https://github.com/Yonkoo11/redline">Source</a>
    <a href="https://x.com/useredline">@useredline</a>
    <span>The AnsemHack Clawrena</span>
  </footer>
</div>

<style>
  .wrap{max-width:1180px;margin:0 auto;padding:0 var(--s6)}

  .masthead{display:flex;align-items:center;gap:var(--s4);padding:var(--s6) 0 var(--s4);
            border-bottom:2px solid var(--ink)}
  .brand{display:flex;align-items:center;gap:var(--s3);text-decoration:none;margin-right:auto}
  .brandmark{width:26px;height:26px;flex:none}
  .brandword{font:800 22px/1 "Barlow Condensed",sans-serif;letter-spacing:-.01em}

  nav{display:flex;gap:var(--s5,20px);flex-wrap:wrap}
  nav a{font:600 13px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;
        color:var(--ink-3);text-decoration:none;padding:var(--s2) 0;border-bottom:2px solid transparent;
        transition:color var(--t-fast) var(--ease),border-color var(--t-fast) var(--ease)}
  @media(hover:hover){nav a:hover{color:var(--ink)}}
  nav a:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}
  nav a.on{color:var(--ink);border-bottom-color:var(--red)}

  footer{padding:var(--s8) 0;margin-top:var(--s16);border-top:2px solid var(--ink);
         display:flex;gap:var(--s4);flex-wrap:wrap;font-size:13px;color:var(--ink-3)}
  footer a{text-decoration:none;border-bottom:1px solid var(--rule);
           transition:color var(--t-fast) var(--ease),border-color var(--t-fast) var(--ease)}
  @media(hover:hover){footer a:hover{color:var(--ink);border-color:var(--red)}}
  footer a:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(224,58,47,.35);border-radius:var(--r-sm)}

  @media (max-width:560px){
    .masthead{flex-wrap:wrap;gap:var(--s3)}
    nav{width:100%;gap:var(--s4)}
  }
</style>
