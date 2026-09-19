// Record the browser shots for the demo video. Playwright records the page and only the page,
// so nothing else on the desktop can end up in the frame. A window grab has leaked twice.
//
//   node tools/record-browser.mjs                 # shots 1, 2 and 6
//   node tools/record-browser.mjs <refusal-sig> <fill-sig>   # adds shot 4, the Solscan proof
//
// Output: demo/shot-<n>.webm, 1920x1080, 25fps. Remux to h264 before editing.
import { chromium } from "playwright";
import { mkdirSync, readdirSync, renameSync } from "node:fs";
import { join } from "node:path";

const SITE = "https://useredline.xyz/";
const OUT = "demo";
const [refusalSig, fillSig] = process.argv.slice(2);

// SHOTS=shot-4b-fill node tools/record-browser.mjs ... re-records one shot instead of all of them.
const only = process.env.SHOTS ? process.env.SHOTS.split(",") : null;

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });

async function shot(name, body) {
  if (only && !only.includes(name)) return;
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } },
  });
  const page = await ctx.newPage();
  await body(page);
  await ctx.close();
  const raw = readdirSync(OUT).filter((f) => f.startsWith("page@"));
  renameSync(join(OUT, raw[0]), join(OUT, `${name}.webm`));
  console.log(`${name}.webm`);
}

const settle = (page) => page.waitForTimeout(1500);

// Every shot below is recorded with slack on the end. The voice take sets the real length and
// the edit trims to it, rather than the voice being squeezed to fit a clip.
//
// The opener. It holds on the dial for the whole opening narration, because that narration is
// ABOUT the dial: the balance, the cap under it, the money being real. An earlier version eased
// down into the tape halfway through and left the narration describing something no longer on
// screen. The drift is small on purpose, a few hundred pixels over half a minute, enough that
// the frame is not dead and not enough to lose the subject.
await shot("shot-2-dial", async (page) => {
  await page.goto(SITE, { waitUntil: "networkidle" });
  await page.waitForTimeout(4000);           // the page settles and the needle sweeps
  for (let i = 0; i < 30; i++) {
    await page.mouse.wheel(0, 11);
    await page.waitForTimeout(880);
  }
  await page.waitForTimeout(4000);
});

// Shot 4: the proof. The refusal's memo on chain, then the fill that followed it.
// Only runs when the signatures from the take are passed in.
// explorer.solana.com, not Solscan. Solscan sits behind a Cloudflare bot check that shows
// "Verify you are human" to an automated browser, and defeating that is not on the table. The
// official explorer serves the same transaction, renders the memo as readable text, and is the
// explorer a judge is least likely to argue with.
async function explorer(name, sig, findText, tab) {
  await shot(name, async (page) => {
    await page.goto(`https://explorer.solana.com/tx/${sig}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(7000);
    if (tab) {
      // The tabs are in-page anchors (href="#tokens"), not a router. The balance that actually
      // moved lives down there, not in the summary at the top.
      await page.locator(`a[href="#${tab}"]`).first().click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(3000);
    }
    if (findText) {
      // Short timeout on purpose. The default is 30 seconds, and a target that never becomes
      // actionable quietly turned a 13 second shot into a 44 second one.
      const target = page.getByText(findText, { exact: false }).first();
      await target.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(1200);
    }
    await page.waitForTimeout(5000);
  });
}
if (refusalSig) await explorer("shot-4a-refusal", refusalSig, "redline:refused");
if (fillSig) await explorer("shot-4b-fill", fillSig, null, "tokens");

// Shot 6: the page, held still. No end-card.
await shot("shot-6-hold", async (page) => {
  await page.goto(SITE, { waitUntil: "networkidle" });
  await page.waitForTimeout(15000);
});

// No vertical social clip. Playwright records the page at CSS pixels and pads the rest of the
// frame, so a 1080x1920 request put a 390-wide phone layout in the corner of a grey canvas.
// Cropping the real region and upscaling it 2.8x to 1080 wide is visibly soft on type, and a
// soft asset is worse than no asset. The 1920x1080 cut plays fine in an X timeline.

await browser.close();
