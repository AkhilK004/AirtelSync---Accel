// Browser smoke test (375x812, advisor -> quote -> toggle -> checkout -> kyc). Not part of the web deps.
// Setup: API on :8000 (LLM_PROVIDER=fake) + web on :3000 (npm run build && npm start); `npm i playwright-core` in a scratch dir; Chrome installed.
// Run: node e2e_web.mjs en   |   node e2e_web.mjs hi   (screenshots go to /tmp/pw)
import { chromium } from "playwright-core";
const loc = process.argv[2] || "en";
const msg = loc === "hi" ? "Meri kirana dukaan hai Jaipur mein, 2 log kaam karte hain" : "I run a clinic in Mumbai, 6 staff, 1 clinic, GST yes";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true });
const p = await ctx.newPage();
const errs = []; p.on("pageerror", e => errs.push("pageerror " + e.message)); p.on("console", m => { if (m.type() === "error") errs.push("console " + m.text()); });
const shot = n => p.screenshot({ path: `/tmp/pw/${loc}-${n}.png` });
await p.goto(`http://localhost:3000/${loc}?partner=ABC`); await shot("1-landing");
await p.locator("form button[type=submit]").click(); // landing: the single "find my plan" button
await p.waitForURL(/advisor/); await p.getByText(loc === "hi" ? "बिज़नेस" : "business", {exact:false}).first().waitFor({ timeout: 15000 }); await shot("2-advisor-start");
await p.fill("input[type=text], input:not([type])", msg); await p.keyboard.press("Enter");
if (loc === "hi") { await p.waitForTimeout(1500); await p.fill("input:not([type])", "1"); await p.keyboard.press("Enter"); await p.waitForTimeout(1500); await p.fill("input:not([type])", "haan GST hai"); await p.keyboard.press("Enter"); }
await p.getByText(/₹/).first().waitFor({ timeout: 20000 }); await p.waitForTimeout(500); await shot("3-recommendation");
const total1 = await p.getByText(/₹[0-9,.]+/).first().innerText();
await p.locator("button").filter({ hasText: loc === "hi" ? "पूरी कीमत" : "See full price" }).last().click();
await p.waitForURL(/quote\//); await p.waitForSelector("[role=switch]", { timeout: 15000 }); await shot("4-quote");
const big = () => p.locator(".slip [aria-live=polite] .font-display").innerText();
const before = await big();
await p.locator("[role=switch]").first().click(); await p.waitForTimeout(1500); await shot("5-quote-toggled");
const after = await big();
await p.locator("button[aria-expanded]").click(); await p.waitForTimeout(300); await shot("6-breakdown");
await p.locator("a").filter({ hasText: loc === "hi" ? "आगे बढ़ें" : "Continue" }).last().click();
await p.waitForURL(/checkout\//); await p.waitForSelector("input[inputmode=numeric]"); 
await p.fill("input[inputmode=numeric] >> nth=0", "9876543210");
await p.locator("button").filter({ hasText: loc === "hi" ? "OTP भेजें" : "Send OTP" }).click();
await p.waitForSelector("input[autocomplete=one-time-code]"); await p.fill("input[autocomplete=one-time-code]", "123456");
await p.fill("input[autocomplete=organization]", "Ravi Traders"); await p.fill("input[autocomplete=street-address]", "12 Market Road, Jaipur");
await shot("7-checkout");
await p.locator("button").filter({ hasText: loc === "hi" ? "ऑर्डर दें" : "Place order" }).click();
await p.waitForURL(/kyc\//, { timeout: 15000 }); await shot("8-kyc");
const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ loc, recTotal: total1, before, after, changed: before !== after, url: p.url(), horizontalOverflow: overflow, errs }));
await b.close();
