// Browser test of the order tracker at 375x812: create an order via API, open /track?demo=1, advance it step by step, reschedule, view messages.
// Setup as e2e_kyc.mjs (API :8000 with LLM_PROVIDER=fake, web :3000 built with NEXT_PUBLIC_DEMO_ADMIN_TOKEN=change-me). Run: node e2e_track.mjs <locale>
import { chromium } from "playwright-core";
const loc = process.argv[2] || "en";
const API = "http://127.0.0.1:8000";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true });
const p = await ctx.newPage();
const errs = [];
p.on("pageerror", (e) => errs.push("pageerror " + e.message));
p.on("console", (m) => m.type() === "error" && errs.push("console " + m.text()));
const shot = (n) => p.screenshot({ path: `C:/tmp/pw/track-${loc}-${n}.png` });
const j = (path, body) => fetch(API + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());

const q = await j("/quotes", { business_type: "Dental clinic", employees: 6, locations: 1, city_tier: 1, gstin_status: "active" });
const o = await j("/checkout", { quote_id: q.id, phone: "9876543210", otp: "123456", business_name: "Neelgiri Physio Clinic", address: "12 Market Road, Mumbai",
  slot_date: "2026-07-18", slot_window: "morning", payment_mode: "pay_on_activation", language: loc });
await p.addInitScript(([id]) => sessionStorage.setItem(`order:${id}:last4`, "3210"), [o.order_id]);

await p.goto(`http://localhost:3000/${loc}/track/${o.order_id}?demo=1`);
await p.locator("[data-status]").first().waitFor({ timeout: 15000 });
await shot("1-placed");
const statuses = async () => p.locator("[data-status]").evaluateAll((els) => els.map((e) => e.getAttribute("data-status")));
const first = await statuses();
const adv = p.locator("main button").filter({ hasText: loc === "en" ? "Demo" : "डेमो" });
for (let i = 0; i < 2; i++) { await adv.click(); await p.waitForTimeout(700); }
await shot("2-install-scheduled");
const mid = await statuses();
await adv.click(); await p.waitForTimeout(700);
await shot("3-technician");
const tech = await p.getByText({ en: "Technician", hi: "टेक्नीशियन", mr: "टेक्निशियन" }[loc], { exact: true }).count();
await p.locator("[role=tab]").nth(1).click(); await p.waitForTimeout(300);
await shot("4-messages");
const msgs = await p.locator("main ul li").count();
await p.locator("[role=tab]").nth(0).click();
await p.locator("main button").filter({ hasText: { en: "Reschedule", hi: "समय बदलें", mr: "वेळ बदला" }[loc] }).click(); await p.waitForTimeout(500);
await shot("5-reschedule");
await p.keyboard.press("Escape");
await adv.click(); await p.waitForTimeout(500); await adv.click(); await p.waitForTimeout(700);
await shot("6-active");
const last = await statuses();
const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
// wrong last4 asks again
const p2 = await ctx.newPage();
await p2.goto(`http://localhost:3000/${loc}/track/${o.order_id}`);
console.log(JSON.stringify({ loc, first, mid, techCardVisible: tech > 0, messageRows: msgs, last, horizontalOverflow: overflow, errs }));
await b.close();
