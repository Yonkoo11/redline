// Record the browser shots for the demo video. Playwright records the page and only the page,
// so nothing else on the desktop can end up in the frame. A window grab has leaked twice.
//
//   node tools/record-browser.mjs                 # shots 1, 2 and 6
//   node tools/record-browser.mjs <refusal-sig>   # adds shot 4, the Solscan proof
//
// Output: demo/shot-<n>.webm, 1920x1080, 25fps. Remux to h264 before editing.
import { chromium } from "playwright";
import { mkdirSync, readdirSync, renameSync } from "node:fs";
import { join } from "node:path";

const SITE = "https://useredline.xyz/";
const OUT = "demo";
const sig = process.argv[2] || null;

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });

async function shot(name, body) {
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

// Shot 1: the problem. A real scroll to the measured ClawPump fact, at reading speed.
await shot("shot-1-problem", async (page) => {
  await page.goto(SITE, { waitUntil: "networkidle" });
  await settle(page);
  for (let i = 0; i < 9; i++) { await page.mouse.wheel(0, 100); await page.waitForTimeout(220); }
  await page.waitForTimeout(3500);
});

// Shot 2: the dial. Reload so the needle sweeps to the live reading on camera.
await shot("shot-2-dial", async (page) => {
  await page.goto(SITE, { waitUntil: "networkidle" });
  await page.waitForTimeout(6000);
});

// Shot 4: the proof, only when a signature from the take is passed in.
if (sig) {
  await shot("shot-4-proof", async (page) => {
    await page.goto(`https://solscan.io/tx/${sig}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(7000);
    for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, 150); await page.waitForTimeout(250); }
    await page.waitForTimeout(4000);
  });
}

// Shot 6: the page, held still. No end-card.
await shot("shot-6-hold", async (page) => {
  await page.goto(SITE, { waitUntil: "networkidle" });
  await page.waitForTimeout(9000);
});

await browser.close();
