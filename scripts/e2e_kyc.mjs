// Browser test of consent + Smart KYC at 375x812. Setup: API :8000 (LLM_PROVIDER=fake), web :3000 (npm run build && npm start),
// `npm i playwright-core` in a scratch dir, Chrome installed.  Run: node e2e_kyc.mjs <locale> <applicant> <gstin> [specimen dir]
import { chromium } from "playwright-core";
const [loc = "en", applicant = "K11", gstin = "03KGZXT1320R1ZZ", dir = "C:/Users/Akhil/Desktop/Airtel/data/raw/kyc_documents"] = process.argv.slice(2);
const API = "http://127.0.0.1:8000";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true });
const p = await ctx.newPage();
const errs = [];
p.on("pageerror", (e) => errs.push("pageerror " + e.message));
p.on("console", (m) => m.type() === "error" && !m.text().includes("403") && errs.push("console " + m.text()));
const shot = (n) => p.screenshot({ path: `C:/tmp/pw/kyc-${loc}-${applicant}-${n}.png` });

// create a quote + order through the API (checkout UI is covered by e2e_web.mjs)
const q = await (await fetch(`${API}/quotes`, { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ business_type: "Kirana store", employees: 2, locations: 1, city_tier: 2, gstin_status: "active" }) })).json();
const o = await (await fetch(`${API}/checkout`, { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ quote_id: q.id, phone: "9876543210", otp: "123456", business_name: "Demo Biz", address: "12 Market Road, Jaipur",
    slot_date: "2026-07-17", slot_window: "morning", payment_mode: "pay_on_activation", language: loc }) })).json();

await p.goto(`http://localhost:3000/${loc}/kyc/${o.order_id}`);
await p.locator("[role=switch]").first().waitFor({ timeout: 15000 });
await shot("1-consent");
const agree = p.locator("button").filter({ has: p.locator("xpath=.") }).last();
const before = await agree.isDisabled();
await p.locator("[role=switch]").nth(0).click(); await p.locator("[role=switch]").nth(1).click();
await shot("2-consent-ticked");
await agree.click();
await p.getByRole("button").nth(3).waitFor(); // registration step buttons
await p.locator("main button:not([disabled])").first().click(); // "Yes, I have GSTIN"
await p.locator("input").first().fill(gstin);
await p.locator("main button:not([disabled])").filter({ hasNot: p.locator("svg") }).last().click(); // look up
await p.waitForTimeout(1500); await shot("3-lookup");
await p.locator("main button:not([disabled])").last().click(); // continue (fixed bar)
await p.locator("input[type=file]").first().waitFor({ state: "attached" });
for (const slot of ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]) {
  const f = `${dir}/${applicant}_${slot}.png`;
  try { await p.locator(`input[data-slot=${slot}]`).setInputFiles(f); await p.waitForTimeout(900); } catch { /* optional doc may not exist */ }
}
await shot("4-uploaded");
await p.locator("main button:not([disabled])").last().click(); // check my documents
await p.getByRole("status").waitFor({ timeout: 15000 }); await p.waitForTimeout(400);
await shot("5-result");
const banner = await p.getByRole("status").innerText();
const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ loc, applicant, agreeWasDisabledBeforeTicking: before, banner, horizontalOverflow: overflow, errs }));
await b.close();
