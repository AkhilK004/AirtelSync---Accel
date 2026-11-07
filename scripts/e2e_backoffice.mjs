// Browser test of /backoffice at desktop (1280x900) and phone (375x812) widths. Setup: API :8000 with SEED_ON_START=true LLM_PROVIDER=fake,
// web :3000 (built with NEXT_PUBLIC_DEMO_ADMIN_TOKEN=change-me). Run: node e2e_backoffice.mjs
import { chromium } from "playwright-core";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const errs = [];
async function run(name, viewport) {
  const ctx = await b.newContext({ viewport });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errs.push(name + " pageerror " + e.message));
  p.on("console", (m) => m.type() === "error" && !m.text().includes("401") && errs.push(name + " console " + m.text()));
  await p.goto("http://localhost:3000/backoffice");
  await p.locator("input[type=password]").fill("wrong"); await p.getByRole("button", { name: "Sign in" }).click();
  const denied = await p.getByRole("alert").isVisible();
  await p.locator("input[type=password]").fill("change-me"); await p.getByRole("button", { name: "Sign in" }).click();
  await p.locator("tbody tr").first().waitFor({ timeout: 15000 });
  await p.screenshot({ path: `C:/tmp/pw/bo-${name}-1-list.png`, fullPage: name === "desktop" });
  const rows = await p.locator("tbody tr").count();
  const scores = await p.locator("tbody tr td:first-child span").allInnerTexts();
  await p.locator("select[aria-label=Route]").selectOption("field_sales"); await p.waitForTimeout(800);
  const field = await p.locator("tbody tr").count();
  await p.locator("select[aria-label=Route]").selectOption(""); await p.waitForTimeout(600);
  await p.locator("tbody tr").first().click(); await p.waitForTimeout(800);
  await p.screenshot({ path: `C:/tmp/pw/bo-${name}-2-drawer.png` });
  const reasons = await p.getByText("Why this score").count();
  await p.getByRole("button", { name: "Mark contacted" }).click(); await p.waitForTimeout(800);
  const marked = await p.getByRole("button", { name: "Mark contacted" }).evaluate((e) => e.className.includes("bg-primary"));
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log(JSON.stringify({ name, denied, rows, topScores: scores.slice(0, 4), fieldRows: field, drawerShowsReasons: reasons > 0, statusMarked: marked, pageOverflow: overflow }));
  await ctx.close();
}
await run("desktop", { width: 1280, height: 900 });
await run("phone", { width: 375, height: 812 });
console.log(JSON.stringify({ errs }));
await b.close();
