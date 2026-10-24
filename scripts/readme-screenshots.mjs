// README screenshots of the real UI, taken in a fresh synthetic environment. See docs/README-SCREENSHOTS.md.
//
//   node scripts/readme-screenshots.mjs --lang zh-CN|en --out <dir> [--ocr-python <python.exe>] [--video]
//
// Creates and stops its own synthetic database and server; never attaches to an existing instance.
// It walks the shared sample order (samples/purchase-orders) through upload, review, partial delivery,
// item collection and a reconciliation draft, taking one screenshot per stage.
import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { once } from "node:events";
import { access, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import http from "node:http";
import { createRequire } from "node:module";
import net from "node:net";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";
import { parseArgs, promisify } from "node:util";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { values: args } = parseArgs({ options: {
  lang: { type: "string", default: "zh-CN" }, "ocr-python": { type: "string" },
  out: { type: "string" }, video: { type: "boolean", default: false },
} });
assert.ok(args.out, "Required: --out");
assert.ok(["zh-CN", "en"].includes(args.lang), "--lang must be zh-CN or en");

const { chromium } = createRequire(import.meta.url)(process.env.FACTORYFLOW_PLAYWRIGHT_PATH ?? "playwright");
const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const env = { ...process.env, PYTHONPATH: path.join(root, "apps/api/src"), PYTHONDONTWRITEBYTECODE: "1" };
const sample = JSON.parse(await readFile(path.join(root, "samples/purchase-orders/purchase-order.json"), "utf8"));
assert.equal(sample.synthetic, true);
const en = args.lang === "en";
const source = path.join(root, "samples/purchase-orders", en ? "purchase-order-en.png" : "purchase-order-zh.png");
const buyer = en ? sample.buyer.en : sample.buyer.zh;
const delivered = ["30", "80", "10.25", "12"];

// UI labels: the Chinese source text, translated through the app's own English catalog.
const catalogText = await readFile(path.join(root, "apps/web/src/messages.en.ts"), "utf8");
const catalog = JSON.parse(catalogText.slice(catalogText.indexOf("{", catalogText.indexOf("=")), catalogText.lastIndexOf("}") + 1));
const L = (key, params = []) => {
  const pattern = en ? catalog[key] ?? key : key;
  return pattern.replace(/\{(\d+)\}/g, (_, index) => String(params[Number(index)] ?? ""));
};
const exact = { exact: true };

await mkdir(args.out, { recursive: true });
const prefix = en ? "en" : "zh";
const shots = [], corrections = [], pageErrors = [], consoleErrors = [], httpErrors = [], externalRequests = [];
const environment = await mkdtemp(path.join(os.tmpdir(), "factoryflow-business-"));
const helper = action => promisify(execFile)(python, ["scripts/business-smoke-env.py", action, "--root", environment],
  { cwd: root, env, windowsHide: true, timeout: 120000 });
let extraction, completed = false, browser, child, base, credentials, app, serverLog = "", serverError;

async function startEnvironment() {
  await helper("prepare");
  const configPath = path.join(environment, "app.json");
  app = JSON.parse(await readFile(configPath, "utf8"));
  if (args["ocr-python"]) {
    await access(args["ocr-python"]);
    app.ocr_engine = "rapid";
    app.ocr_python = path.resolve(args["ocr-python"]);
    await writeFile(configPath, JSON.stringify(app, null, 2) + "\n");
  }
  credentials = JSON.parse(await readFile(path.join(environment, "client.json"), "utf8"));
  const listener = net.createServer(); listener.listen(0, "127.0.0.1"); await once(listener, "listening");
  const port = listener.address().port;
  await new Promise((resolve, reject) => listener.close(error => error ? reject(error) : resolve()));
  base = `http://127.0.0.1:${port}`;
  child = spawn(python, ["scripts/offline-smoke-server.py", "--config", configPath, "--port", String(port)],
    { cwd: root, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  child.on("error", error => { serverError = error.message; });
  child.stdout.on("data", data => { serverLog += data; }); child.stderr.on("data", data => { serverLog += data; });
  for (let attempt = 0; attempt < 150; attempt++) {
    if (serverError || child.exitCode !== null) throw new Error(`Owned server failed: ${serverError ?? serverLog}`);
    const ready = await new Promise(resolve => {
      const request = http.get(`${base}/api/v1/health/ready`, response => { response.resume(); resolve(response.statusCode === 200); });
      request.on("error", () => resolve(false)); request.setTimeout(500, () => request.destroy());
    });
    if (ready && serverLog.includes(`Uvicorn running on ${base}`)) {
      assert.match(serverLog, /OFFLINE_GUARD_READY:2_NEGATIVE_CONTROLS_BLOCKED/); return;
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("Owned server readiness timed out");
}

async function stopServer() {
  if (!child?.pid || child.exitCode !== null) return;
  const closing = once(child, "exit"); child.kill();
  let timer;
  try { await Promise.race([closing, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("Owned server cleanup timed out")), 6000); })]); }
  finally { clearTimeout(timer); }
}

async function open(viewport, scale) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: scale, locale: en ? "en-US" : "zh-CN", serviceWorkers: "block",
    ...(args.video ? { recordVideo: { dir: args.out, size: viewport } } : {}) });
  await context.addInitScript(locale => { try { localStorage.setItem("factoryflow.locale", locale); } catch { /* storage optional */ } }, args.lang);
  await context.route("**/*", route => {
    if (new URL(route.request().url()).origin === base) return route.continue();
    externalRequests.push(route.request().url()); return route.abort("internetdisconnected");
  });
  await context.routeWebSocket("**/*", socket => { externalRequests.push(socket.url()); socket.close(); });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("console", entry => { if (["error", "warning"].includes(entry.type())) consoleErrors.push({ text: entry.text(), url: entry.location().url }); });
  page.on("response", response => {
    if (response.status() >= 400 && !(response.status() === 401 && new URL(response.url()).pathname === "/api/v1/auth/session"))
      httpErrors.push({ path: new URL(response.url()).pathname, status: response.status() });
  });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByLabel(L("账号"), exact).fill(credentials.username);
  await page.getByLabel(L("密码"), exact).fill(credentials.password);
  await page.getByRole("button", { name: L("登录"), exact: true }).click();
  await page.locator(".workspace").waitFor();
  assert.equal(new URL(page.url()).origin, base);
  assert.equal(await page.title(), en ? "FactoryFlow · Orders and deliveries" : "交有数 · 工厂订单与送货");
  return { context, page };
}

async function shot(page, name, { fullPage = false, scrollTop = true } = {}) {
  await page.evaluate(() => document.fonts.ready);
  if (scrollTop) await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  assert.equal(await page.locator("vite-error-overlay").count(), 0);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${name}: horizontal overflow`);
  const file = path.join(args.out, `${prefix}-${name}.png`);
  await page.screenshot({ path: file, fullPage });
  shots.push(path.basename(file));
}

let desktop, phone;
try {
  await startEnvironment();
  browser = await chromium.launch({ channel: process.env.FACTORYFLOW_BROWSER_CHANNEL ?? "chrome", headless: true,
    proxy: { server: "http://127.0.0.1:9", bypass: "127.0.0.1,localhost" }, args: ["--disable-background-networking"] });
  desktop = await open({ width: 1440, height: 900 }, 1);
  const page = desktop.page;
  for (const endpoint of ["customers", "sources", "materials", "orders/open-lines", "orders/open-lines?status=deleted", "deliveries"]) {
    const response = await desktop.context.request.get(`${base}/api/v1/${endpoint}`);
    assert.equal(response.status(), 200, `Empty-environment check failed: ${endpoint}`);
    const data = await response.json();
    assert.equal((Array.isArray(data) ? data : data.items).length, 0, `Environment is not empty: ${endpoint}`);
  }

  // 01 First run: nothing imported yet.
  await page.getByRole("heading", { name: L("从第一张订单开始"), exact: true }).waitFor()
    .catch(() => { throw new Error("The first-run screen did not appear: use a fresh, empty synthetic environment"); });
  await shot(page, "01-first-run");

  // 02 Original next to the recognized candidate, before any correction.
  await page.locator(".file-drop input[type=file]").setInputFiles(source);
  const extracted = page.waitForResponse(response => /\/api\/v1\/sources\/[^/]+\/extractions$/.test(new URL(response.url()).pathname) && response.request().method() === "POST", { timeout: 180000 });
  await page.getByRole("button", { name: L("上传并识别"), exact: true }).click();
  const extractionResponse = await extracted;
  assert.equal(extractionResponse.status(), 200);
  const extractionJob = await extractionResponse.json();
  const details = await desktop.context.request.get(`${base}/api/v1/extractions/${extractionJob.extraction_id}`);
  assert.equal(details.status(), 200);
  extraction = await details.json();
  await writeFile(path.join(args.out, `${prefix}-raw-extraction.json`), JSON.stringify(extraction, null, 2) + "\n");
  await page.locator(".source-entry-layout").waitFor({ timeout: 180000 });
  await page.locator(".entry-line").first().waitFor();
  await shot(page, "02-source-review", { fullPage: true });

  // Complete the order the way a user would: new customer inline, check every line against the source.
  await page.getByRole("button", { name: L("新建客户"), exact: true }).click();
  await page.getByLabel(L("客户完整名称")).fill(buyer);
  await page.getByRole("button", { name: L("创建客户"), exact: true }).click();
  await page.locator("#order-customer").waitFor();
  const field = async (label, value, locator) => {
    const current = await locator.inputValue();
    if (current !== value) { corrections.push({ field: label, recognized: current, corrected: value }); await locator.fill(value); }
  };
  await field("order_number", sample.order_number, page.getByLabel(L("客户订单号"), exact));
  await field("business_date", sample.order_date, page.getByLabel(L("订单日期"), exact));
  const recognizedCurrency = await page.locator("#order-currency").inputValue();
  if (recognizedCurrency !== "CNY") {
    corrections.push({ field: "currency", recognized: recognizedCurrency, corrected: "CNY" });
    await page.locator("#order-currency").selectOption("CNY");
  }
  const rows = page.locator(".entry-line");
  const recognizedLineCount = extraction.candidate.lines.length;
  if (recognizedLineCount !== sample.lines.length)
    corrections.push({ field: "line_count", recognized: recognizedLineCount, corrected: sample.lines.length, method: "manual transcription against the synthetic original, after the raw screenshot" });
  while (await rows.count() < sample.lines.length)
    await page.getByRole("button", { name: L("添加明细"), exact: true }).click();
  while (await rows.count() > sample.lines.length)
    await rows.last().getByRole("button", { name: L("删除第 {0} 行", [await rows.count()]), exact: true }).click();
  for (const [index, line] of sample.lines.entries()) {
    const row = rows.nth(index);
    await field(`line ${index + 1} code`, line.internal_item_code, row.locator(".item-code-field input"));
    await field(`line ${index + 1} name`, en ? line.name_en : line.name_zh, row.locator(".item-name-field textarea"));
    await field(`line ${index + 1} specification`, line.specification, row.locator(".specification-field textarea"));
    await field(`line ${index + 1} quantity`, line.quantity, row.getByLabel(L("数量"), exact));
    await field(`line ${index + 1} unit`, line.unit, row.getByLabel(L("单位"), exact));
    await field(`line ${index + 1} price`, line.unit_price, row.getByLabel(L("订单单价"), exact));
    await field(`line ${index + 1} source amount`, line.amount, row.getByLabel(L("原单金额"), exact));
  }
  await page.locator(".form-submit button").click();
  await page.getByRole("heading", { name: L("核对订单"), exact: true }).waitFor();
  await shot(page, "02b-manually-reviewed", { fullPage: true });
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: L("确认生成订单"), exact: true }).click();
  await page.getByRole("heading", { name: sample.order_number, exact: true }).waitFor();

  // Partial delivery: 30 PCS, 80 PCS, 10.25 KG, 12 M.
  await page.getByRole("button", { name: L("登记送货"), exact: true }).click();
  await page.getByLabel(L("送货日期"), exact).fill("2026-11-05");
  const quantities = page.locator(`input[aria-label$="${L("{0} 本次送货", [""]).trim()}"]`);
  assert.equal(await quantities.count(), delivered.length);
  for (const [index, value] of delivered.entries()) await quantities.nth(index).fill(value);
  await page.getByRole("button", { name: L("确认实际送货"), exact: true }).click();
  await page.getByRole("heading", { name: L("送货详情"), exact: true }).waitFor();

  // 03 Outstanding quantities after the delivery.
  await page.getByRole("button", { name: L("待交清单"), exact: true }).click();
  await page.locator(".desktop-lines tbody tr").nth(1).waitFor();
  const remaining = await page.locator(".desktop-lines td.remaining").allInnerTexts();
  assert.deepEqual(remaining.map(text => text.trim()), ["90", "160", "25.25", "36"]);
  await shot(page, "03-open-lines");

  // 04 Order detail: collect the first two lines into the item catalog so the summary shows 2 / 4.
  await page.locator(".desktop-lines .text-button").first().click();
  await page.getByRole("heading", { name: sample.order_number, exact: true }).waitFor();
  await page.locator(".material-summary-actions button").click();
  for (let count = 0; count < 2; count++) {
    await page.getByRole("button", { name: L("收录为新物料"), exact: true }).first().click();
    await page.locator(".material-chip").nth(count).waitFor();
  }
  await page.locator(".material-summary-actions button").click();
  await page.locator(".material-chip").nth(1).waitFor();
  await shot(page, "04-order-detail", { fullPage: true });

  // 05 Reconciliation draft for November (784.40 CNY of delivered goods).
  await page.getByRole("button", { name: L("客户对账"), exact: true }).click();
  await page.locator("select").filter({ has: page.locator("option", { hasText: buyer }) }).first().selectOption({ label: buyer });
  await page.getByText(L("该客户还没有对账记录。选择期间，从送货明细开始。"), exact).waitFor();
  await page.getByLabel(L("开始日期"), exact).fill("2026-11-01");
  await page.getByLabel(L("结束日期"), exact).fill("2026-11-30");
  await page.getByRole("button", { name: L("开始本期对账"), exact: true }).click();
  await page.getByRole("button", { name: L("加入"), exact: true }).first().waitFor();
  assert.equal(await page.getByRole("button", { name: L("加入"), exact: true }).count(), sample.lines.length);
  for (let index = 0; index < sample.lines.length; index++) {
    // Adding a row collapses the candidate list; reopen it only if necessary.
    if (!(await page.getByRole("button", { name: L("加入"), exact: true }).first().isVisible())) await page.locator(".statement-candidates summary").click();
    await page.getByRole("button", { name: L("加入"), exact: true }).first().click();
  }
  await page.locator(".statement-bottom .statement-options summary").click();
  await page.locator(".statement-bottom .statement-filters select").selectOption("included");
  await page.locator(".statement-bottom .statement-options summary").click();
  await page.getByRole("button", { name: L("保存草稿"), exact: true }).click();
  await page.locator(".statement-total dd").filter({ hasText: /^784\.40$/ }).waitFor();
  assert.ok(await page.locator(".statement-lines-compact th").evaluateAll(cells => cells.every(cell => cell.scrollWidth <= cell.clientWidth)), "Reconciliation column headings fit their cells");
  await shot(page, "05-statement", { fullPage: true });

  // Phone: the outstanding list at 390 px.
  phone = await open({ width: 390, height: 844 }, 2);
  await phone.page.locator(".mobile-lines article").first().waitFor();
  for (const name of ["待交清单", "收订单", "送货记录", "客户对账", "更多"])
    assert.equal(await phone.page.getByRole("navigation").getByRole("button", { name: L(name), exact: true }).count(), 1);
  await phone.page.getByRole("button", { name: L("更多"), exact: true }).click();
  await phone.page.getByRole("button", { name: L("物料池"), exact: true }).click();
  await phone.page.getByRole("heading", { name: L("物料池"), exact: true }).waitFor();
  await phone.page.getByRole("button", { name: L("待交清单"), exact: true }).click();
  await phone.page.locator(".mobile-lines article").first().waitFor();
  await phone.page.locator(".mobile-lines .delivery-progress").first().evaluate(element => element.scrollIntoView({ block: "center" }));
  const bar = await phone.page.locator(".mobile-lines .delivery-progress").first().boundingBox();
  const nav = await phone.page.getByRole("navigation").boundingBox();
  assert.ok(bar && nav && bar.y >= 0 && bar.y + bar.height <= nav.y, "Phone progress bar is visible above the fixed navigation");
  await shot(phone.page, "03-open-lines-phone", { scrollTop: false });

  assert.deepEqual(pageErrors, [], "Page errors during capture");
  assert.deepEqual(httpErrors, [], "HTTP errors during capture");
  assert.deepEqual(externalRequests, [], "Unexpected external requests");
  assert.ok(!serverLog.includes("OFFLINE_UNEXPECTED_EGRESS:"), "Unexpected server egress");
  assert.deepEqual(consoleErrors.filter(entry => !(/401/.test(entry.text) && /\/api\/v1\/auth\/session$/.test(entry.url))), [], "Console errors during capture");
  completed = true;
} catch (error) {
  if (desktop?.page) {
    await desktop.page.screenshot({ path: path.join(args.out, `${prefix}-failure.png`), fullPage: true }).catch(() => {});
    await writeFile(path.join(args.out, `${prefix}-failure.txt`), await desktop.page.locator("body").innerText()).catch(() => {});
  }
  throw error;
} finally {
  const cleanupErrors = [];
  for (const close of [() => desktop?.context.close(), () => phone?.context.close(), () => browser?.close(), stopServer,
    async () => { if (await access(path.join(environment, "private-state.json")).then(() => true, () => false)) await helper("stop"); }]) {
    try { await close(); } catch (error) { cleanupErrors.push(String(error)); }
  }
  completed = completed && cleanupErrors.length === 0;
  await writeFile(path.join(environment, "capture-server.log"), serverLog);
  await writeFile(path.join(args.out, `${prefix}-capture.json`), JSON.stringify({ completed, lang: args.lang, base, environment, ocr_engine: app?.ocr_engine ?? "windows", recognized_line_count: extraction?.candidate?.lines?.length, shots, corrections, pageErrors, consoleErrors, httpErrors, externalRequests, blocked_windows_version_probes: (serverLog.match(/OFFLINE_BLOCKED_WINDOWS_VERSION_PROBE/g) ?? []).length, cleanupErrors, extraction_status: extraction?.status }, null, 2) + "\n");
  assert.deepEqual(cleanupErrors, [], "Synthetic environment cleanup failed");
}
console.log(`${shots.length} screenshots in ${args.out}; ${corrections.length} recognized fields corrected (see ${prefix}-capture.json).`);
