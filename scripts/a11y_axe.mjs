// Accessibility audit with axe-core on every owner screen (en/hi/mr, 375 and 1280 px). Setup: API :8000 (LLM_PROVIDER=fake), web :3000 built; `npm i playwright-core axe-core` in a scratch dir. Run: node a11y_axe.mjs
import { chromium } from "playwright-core";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const axeSrc = require("fs").readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const API = "http://127.0.0.1:8000";
const j = async (path, body) => (await fetch(API + path, { method: body ? "POST" : "GET", headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined })).json();
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const rows = []; const seen = new Set();
async function audit(p, name) {
  await p.addScriptTag({ content: axeSrc });
  const r = await p.evaluate(async () => await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] } }));
  for (const v of r.violations) {
    const key = name + "|" + v.id; if (seen.has(key)) continue; seen.add(key);
    rows.push({ page: name, id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, sample: v.nodes[0].html.slice(0, 140), target: v.nodes[0].target.join(" ") });
  }
}
for (const loc of ["en", "hi", "mr"]) {
  const q = await j("/quotes", { business_type: "Dental clinic", employees: 6, locations: 1, city_tier: 1, gstin_status: "active" });
  const meta = await j("/meta"); const d = new Date(meta.today); d.setDate(d.getDate() + 2);
  const o = await j("/checkout", { quote_id: q.id, phone: "9876543210", otp: "123456", business_name: "Test", address: "12 Market Road", slot_date: d.toISOString().slice(0, 10), slot_window: "morning", payment_mode: "pay_on_activation", language: loc });
  for (const [vw, w, h] of [["375", 375, 812], ["1280", 1280, 900]]) {
    const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage();
    const go = async (path, name, wait = 1500) => { await p.goto(`http://localhost:3000/${loc}${path}`); await p.waitForTimeout(wait); await audit(p, `${loc}/${vw}/${name}`); };
    await go("", "landing");
    await go("/advisor", "advisor");
    await go(`/quote/${q.id}`, "quote");
    await go(`/checkout/${q.id}`, "checkout");
    await go(`/kyc/${o.order_id}`, "kyc-consent", 2000);
    await go(`/track/${o.order_id}?demo=1`, "track-gate");
    await p.context().close();
  }
}
await b.close();
const by = {}; for (const r of rows) (by[r.id + " [" + r.impact + "] " + r.help] ??= []).push(r);
for (const [k, v] of Object.entries(by)) { console.log("\n" + k + "  on " + v.length + " page(s)"); console.log("   e.g. " + v[0].page + " :: " + v[0].target + " :: " + v[0].sample); }
console.log("\nTOTAL distinct violations:", rows.length);
