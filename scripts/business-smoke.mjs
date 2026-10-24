// Synthetic, prepared-environment browser + API + PostgreSQL smoke. No system network changes.
import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { once } from "node:events";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import http from "node:http";
import { createRequire } from "node:module";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.FACTORYFLOW_PLAYWRIGHT_PATH ?? "playwright");
const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const evidence = await mkdtemp(path.join(os.tmpdir(), "factoryflow-business-"));
const helper = async action => (await promisify(execFile)(python, ["scripts/business-smoke-env.py", action, "--root", evidence], { cwd: root, windowsHide: true, timeout: 120000 })).stdout.trim();
const listener = net.createServer();
listener.listen(0, "127.0.0.1");
await once(listener, "listening");
const port = listener.address().port;
await new Promise((resolve, reject) => listener.close(error => error ? reject(error) : resolve()));
const base = `http://127.0.0.1:${port}`;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const checks = [], logs = [], externalRequests = [], pageErrors = [], consoleErrors = [], httpErrors = [];
let child, browser, context, page, credentials, committed, failed;
let fault = false;
let activeDelivery;

async function startServer(config = "app.json") {
  const log = { text: "", error: null }; logs.push(log);
  child = spawn(python, ["scripts/offline-smoke-server.py", "--port", String(port), "--config", path.join(evidence, config)], { cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  child.on("error", error => { log.error = error.message; });
  child.stdout.on("data", data => { log.text += data.toString(); });
  child.stderr.on("data", data => { log.text += data.toString(); });
  for (let attempt = 0; attempt < 150; attempt++) {
    if (log.error || child.exitCode !== null) throw new Error(`Local server failed: ${log.error ?? log.text}`);
    const ready = await new Promise(resolve => {
      const request = http.get(`${base}/api/v1/health/ready`, response => { response.resume(); resolve(response.statusCode === 200); });
      request.on("error", () => resolve(false)); request.setTimeout(500, () => request.destroy());
    });
    if (ready) { assert.match(log.text, /OFFLINE_GUARD_READY:2_NEGATIVE_CONTROLS_BLOCKED/); return; }
    await sleep(100);
  }
  throw new Error("Local application readiness timed out");
}

async function stopServer() {
  if (!child || child.exitCode !== null) return;
  const closing = once(child, "exit"); child.kill();
  let timer;
  try { await Promise.race([closing, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("Smoke server cleanup timed out")), 6000); })]); }
  finally { clearTimeout(timer); }
}

async function newContext(onExternal = url => externalRequests.push(url)) {
  const fresh = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: "block" });
  fresh.setDefaultTimeout(10000);
  await fresh.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== base) { onExternal(url.href); await route.abort("internetdisconnected"); }
    else await route.continue();
  });
  await fresh.routeWebSocket("**/*", socket => { onExternal(socket.url()); socket.close(); });
  return fresh;
}

function watch(target) {
  target.on("pageerror", error => pageErrors.push(error.message));
  target.on("console", entry => {
    if (entry.type() === "error" || entry.type() === "warning") consoleErrors.push({ text: entry.text(), url: entry.location().url, fault });
  });
  target.on("response", response => { if (response.status() >= 400) httpErrors.push({ path: new URL(response.url()).pathname, status: response.status(), fault }); });
}

async function loginFresh() {
  page = await context.newPage(); watch(page);
  await page.goto(base, { waitUntil: "networkidle" });
  assert.equal(await page.title(), "交有数 · 工厂订单与送货");
  assert.equal(new URL(page.url()).origin, base);
  await page.getByRole("heading", { name: "登录交有数" }).waitFor();
  await page.getByLabel("账号", { exact: true }).fill(credentials.username);
  await page.getByLabel("密码", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.locator(".workspace").waitFor();
}

async function screenshot(name) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${name}: page overflow`);
  assert.equal(await page.locator("vite-error-overlay").count(), 0);
  await page.screenshot({ path: path.join(evidence, name), fullPage: true });
}

async function downloadOriginal() {
  const pending = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载凭证" }).first().click();
  const downloaded = await pending;
  const bytes = await readFile(await downloaded.path());
  assert.equal(createHash("sha256").update(bytes).digest("hex"), committed.sha256);
  assert.equal(JSON.parse(bytes).order.lines[1].source_quantity_text, "2.000");
}

try {
  await helper("prepare");
  credentials = JSON.parse(await readFile(path.join(evidence, "client.json"), "utf8"));
  await startServer();
  browser = await chromium.launch({ channel: process.env.FACTORYFLOW_BROWSER_CHANNEL ?? "chrome", headless: true,
    proxy: { server: "http://127.0.0.1:9", bypass: "127.0.0.1" }, args: ["--disable-background-networking"] });
  const denied = [];
  const probe = await newContext(url => denied.push(url));
  await assert.rejects((await probe.newPage()).goto("https://offline-probe.invalid/"));
  assert.equal(denied.length, 1); await probe.close();
  checks.push("browser_and_python_external_negative_controls_blocked");
  context = await newContext();
  await loginFresh();
  await page.getByRole("heading", { name: "从第一张订单开始" }).waitFor();
  checks.push("fresh_local_login_and_real_empty_database");

  await page.getByRole("button", { name: "直接填写订单", exact: true }).click();
  await page.getByRole("button", { name: "新建客户", exact: true }).click();
  await page.getByLabel("客户完整名称").fill("Synthetic QA Customer");
  await page.getByRole("button", { name: "创建客户", exact: true }).click();
  await page.getByRole("combobox", { name: "客户", exact: true }).selectOption({ label: "Synthetic QA Customer" });
  await page.getByLabel("客户订单号", { exact: true }).fill("SYN-OFFLINE-001");
  await page.getByLabel("订单日期", { exact: true }).fill("2026-09-30");
  await page.getByLabel("币种", { exact: true }).selectOption("CNY");
  const firstLine = page.getByRole("group", { name: "第1 行", exact: true });
  await firstLine.getByLabel("货物名称", { exact: true }).fill("Synthetic precision material");
  await firstLine.getByLabel("数量", { exact: true }).fill("1.125");
  await firstLine.getByLabel("单位", { exact: true }).fill("PCS");
  await firstLine.getByLabel("原单金额", { exact: true }).fill("99.00");
  await page.getByRole("button", { name: "核对订单", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "整数" }).waitFor();
  await firstLine.getByLabel("单位", { exact: true }).fill("KG");
  await page.getByRole("button", { name: "添加明细", exact: true }).click();
  const secondLine = page.getByRole("group", { name: "第2 行", exact: true });
  await secondLine.getByLabel("货物名称", { exact: true }).fill("Synthetic assembly part");
  await secondLine.getByLabel("数量", { exact: true }).fill("2.000");
  await secondLine.getByLabel("单位", { exact: true }).fill("PCS");
  await secondLine.getByLabel("订单单价", { exact: true }).fill("0");
  fault = true;
  await helper("expire-sessions");
  await page.getByRole("button", { name: "核对订单", exact: true }).click();
  const reauth = page.getByRole("dialog", { name: "重新登录" });
  await reauth.waitFor();
  await reauth.getByLabel("密码", { exact: true }).fill(credentials.password);
  await reauth.getByRole("button", { name: "重新登录", exact: true }).click();
  await reauth.waitFor({ state: "hidden" });
  assert.equal(await firstLine.getByLabel("数量", { exact: true }).inputValue(), "1.125");
  assert.equal(await secondLine.getByLabel("数量", { exact: true }).inputValue(), "2.000");
  fault = false;
  checks.push("expired_session_reauthentication_preserves_unsaved_order_input");
  await page.getByRole("button", { name: "核对订单", exact: true }).click();
  await page.getByRole("heading", { name: "核对订单", exact: true }).waitFor();
  assert.ok(await page.getByRole("button", { name: "确认生成订单", exact: true }).isDisabled());
  await screenshot("review-desktop.png");
  await page.getByRole("checkbox").check();
  fault = true;
  await context.route("**/api/v1/orders", async route => {
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    committed = await response.json();
    await route.abort("connectionreset");
  });
  await page.getByRole("button", { name: "确认生成订单", exact: true }).click();
  await page.getByRole("button", { name: "重试本次提交", exact: true }).waitFor();
  assert.ok(await page.getByRole("button", { name: "返回修改", exact: true }).isDisabled());
  await context.unroute("**/api/v1/orders");
  await page.getByRole("button", { name: "重试本次提交", exact: true }).click();
  await page.getByRole("heading", { name: "SYN-OFFLINE-001", exact: true }).waitFor();
  fault = false;
  assert.equal(JSON.parse(await helper("inspect")).orders, 1);
  await downloadOriginal();
  checks.push("explicit_customer_quantity_error_review_manual_confirmation_and_lost_response_replay");
  checks.push("immutable_download_matches_original_sha256_and_source_text");

  await page.getByRole("button", { name: "修订订单", exact: true }).click();
  await page.getByRole("group", { name: "第1 行", exact: true }).getByLabel("数量", { exact: true }).fill("1.250");
  await page.getByLabel("修订原因", { exact: true }).fill("Synthetic revision for verification");
  await page.getByRole("button", { name: "核对订单", exact: true }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认修订", exact: true }).click();
  await page.getByText("确认版本2", { exact: true }).waitFor();
  await downloadOriginal();
  await page.getByRole("button", { name: "删除订单", exact: true }).click();
  await page.getByLabel("操作原因", { exact: true }).fill("Synthetic removal");
  fault = true;
  await context.route(`**/api/v1/orders/${committed.order_id}`, route => route.abort("connectionreset"));
  await page.getByRole("button", { name: "确认删除", exact: true }).click();
  await page.getByRole("alert").waitFor();
  await context.unroute(`**/api/v1/orders/${committed.order_id}`);
  await page.getByRole("button", { name: "刷新订单", exact: true }).click();
  await page.getByRole("button", { name: "恢复订单", exact: true }).waitFor();
  fault = false;
  checks.push("confirmed_status_change_followup_read_failure_recovers_without_resubmitting");
  await page.getByRole("button", { name: "恢复订单", exact: true }).click();
  await page.getByLabel("操作原因", { exact: true }).fill("Synthetic restoration");
  await page.getByRole("button", { name: "确认恢复", exact: true }).click();
  await page.getByText("当前版本4 · CNY 人民币", { exact: true }).waitFor();
  await screenshot("detail-desktop.png");
  checks.push("revision_retains_old_evidence_and_delete_restore_preserves_order_identity");

  await page.getByRole("button", { name: "返回订单", exact: true }).click();
  await page.locator(".list-toolbar select").selectOption({ label: "Synthetic QA Customer" });
  await page.locator(".desktop-lines tbody tr:not(.order-group-heading)").first().waitFor();
  assert.equal(await page.locator(".desktop-lines tbody tr:not(.order-group-heading)").count(), 2);
  await screenshot("orders-desktop.png");
  await page.setViewportSize({ width: 390, height: 844 });
  await screenshot("orders-mobile.png");
  await page.getByRole("button", { name: "查看 SYN-OFFLINE-001 第1行", exact: true }).first().click();
  await page.getByText("当前版本4 · CNY 人民币", { exact: true }).waitFor();
  await screenshot("detail-mobile.png");
  checks.push("real_filtered_undelivered_lines_desktop_and_390px_mobile");

  await page.getByRole("button", { name: "返回订单", exact: true }).click();
  await page.getByRole("button", { name: "刷新明细", exact: true }).waitFor();
  await page.locator(".mobile-lines article").first().waitFor();
  fault = true;
  await context.route("**/api/v1/orders/open-lines?*", route => route.abort("connectionrefused"));
  await page.getByRole("button", { name: "刷新明细", exact: true }).click();
  await page.getByRole("alert").waitFor();
  await context.unroute("**/api/v1/orders/open-lines?*");
  await page.getByRole("button", { name: "刷新明细", exact: true }).click();
  await page.getByRole("alert").waitFor({ state: "hidden" });
  await page.locator(".mobile-lines article").first().waitFor();
  fault = false;
  checks.push("local_api_failure_is_visible_and_refresh_recovers");

  // Exercise delivery entry, committed-but-lost response replay, print and exact reversal.
  await page.getByRole("button", { name: "查看 SYN-OFFLINE-001 第1行", exact: true }).first().click();
  await page.getByRole("button", { name: "登记送货", exact: true }).click();
  await page.getByLabel("送货日期", { exact: true }).fill("2026-10-01");
  await page.getByLabel("Synthetic precision material 本次送货", { exact: true }).fill("0.125");
  await page.getByLabel("Synthetic assembly part 本次送货", { exact: true }).fill("1.000");
  await screenshot("delivery-entry-mobile.png");
  fault = true;
  let createdDelivery;
  await context.route("**/api/v1/deliveries", async route => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch(); assert.equal(response.status(), 200);
    createdDelivery = await response.json(); await route.abort("connectionreset");
  });
  await page.getByRole("button", { name: "确认实际送货", exact: true }).click();
  await page.getByRole("button", { name: "重试本次送货", exact: true }).waitFor();
  assert.ok(await page.getByRole("button", { name: "取消", exact: true }).isDisabled());
  await context.unroute("**/api/v1/deliveries");
  await page.getByRole("button", { name: "重试本次送货", exact: true }).click();
  await page.getByRole("heading", { name: "送货详情", exact: true }).waitFor();
  await page.getByRole("link", { name: "打开打印页", exact: true }).waitFor();
  fault = false;
  assert.equal(JSON.parse(await helper("inspect")).deliveries, 1);
  assert.deepEqual(createdDelivery.lines.map(line => line.quantity), ["0.125", "1"]);
  for (const value of ["0.125", "千克", "件"]) {
    const box = await page.locator(".delivery-detail").getByRole("cell", { name: value, exact: true }).boundingBox();
    assert.ok(box && box.x >= 0 && box.x + box.width <= 390, `mobile delivery cell visible: ${value}`);
  }
  await screenshot("delivery-detail-mobile.png");
  await page.setViewportSize({ width: 1280, height: 900 });
  await screenshot("delivery-detail-desktop.png");
  const popup = page.waitForEvent("popup");
  await page.getByRole("link", { name: "打开打印页", exact: true }).click();
  const printed = await popup; watch(printed); await printed.waitForLoadState("networkidle");
  await printed.emulateMedia({ media: "print" });
  assert.match(await printed.locator("body").innerText(), /0\.125/);
  assert.match(await printed.locator("body").innerText(), /有效送货/);
  await printed.screenshot({ path: path.join(evidence, "delivery-print.png"), fullPage: true });
  await printed.pdf({ path: path.join(evidence, "delivery-print.pdf"), format: "A4", printBackground: true });
  await printed.close();
  await page.getByRole("button", { name: "查看来源订单", exact: true }).click();
  await page.getByText("当前版本5 · CNY 人民币", { exact: true }).waitFor();
  assert.match(await page.locator("table").innerText(), /1\.125/);
  await page.getByRole("button", { name: "送货记录", exact: true }).click();
  await page.getByRole("button", { name: "查看送货", exact: true }).first().click();
  await page.getByRole("button", { name: "作废送货", exact: true }).click();
  await page.getByLabel("作废原因", { exact: true }).fill("Synthetic browser reversal");
  fault = true;
  await context.route(`**/api/v1/deliveries/${createdDelivery.id}/void`, async route => {
    const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort("connectionreset");
  });
  await page.getByRole("button", { name: "确认作废送货", exact: true }).click();
  await page.getByRole("button", { name: "重试本次作废", exact: true }).waitFor();
  await context.unroute(`**/api/v1/deliveries/${createdDelivery.id}/void`);
  await page.getByRole("button", { name: "重试本次作废", exact: true }).click();
  await page.getByText("已作废，数量已回到订单未交。原因：Synthetic browser reversal", { exact: true }).waitFor();
  fault = false;
  await page.getByRole("button", { name: "查看来源订单", exact: true }).click();
  await page.getByText("当前版本6 · CNY 人民币", { exact: true }).waitFor();
  const rows = await page.locator("tbody tr").allTextContents();
  assert.match(rows[0], /1\.25/); assert.match(rows[1], /2/);
  checks.push("normal_delivery_and_void_lost_response_replay_exact_quantities_and_print_v1");
  // Keep a second valid delivery for restart/backup recovery evidence.
  await page.getByRole("button", { name: "登记送货", exact: true }).click();
  await page.getByLabel("送货日期", { exact: true }).fill("2026-10-01");
  await page.getByLabel("Synthetic precision material 本次送货", { exact: true }).fill("0.125");
  const createdResponse = page.waitForResponse(response => response.url() === `${base}/api/v1/deliveries` && response.request().method() === "POST");
  await page.getByRole("button", { name: "确认实际送货", exact: true }).click();
  activeDelivery = await (await createdResponse).json();
  await page.getByRole("link", { name: "打开打印页", exact: true }).waitFor();
  assert.equal(JSON.parse(await helper("inspect")).deliveries, 2);

  await context.close(); await stopServer();
  await helper("restart-database"); await startServer();
  context = await newContext(); await loginFresh();
  await page.locator(".desktop-lines tbody tr:not(.order-group-heading)").first().waitFor();
  assert.match(await page.locator(".desktop-lines").innerText(), /1\.125/);
  await page.getByRole("button", { name: "查看 SYN-OFFLINE-001 第1行", exact: true }).click();
  await page.getByText("确认版本2", { exact: true }).waitFor(); await downloadOriginal();
  checks.push("postgresql_and_api_cold_restart_fresh_browser_offline_login_and_same_evidence");

  const restore = JSON.parse(await helper("restore-check"));
  assert.equal(restore.backup_objects, 2);
  await context.close(); await stopServer(); await startServer("app-restored.json");
  context = await newContext(); await loginFresh();
  await page.locator(".desktop-lines tbody tr:not(.order-group-heading)").first().waitFor();
  assert.equal(await page.locator(".desktop-lines tbody tr:not(.order-group-heading)").count(), 2);
  await page.getByRole("button", { name: "查看 SYN-OFFLINE-001 第1行", exact: true }).click();
  await page.getByText("当前版本7 · CNY 人民币", { exact: true }).waitFor(); await downloadOriginal();
  await page.getByRole("button", { name: "送货记录", exact: true }).click();
  await page.getByRole("button", { name: "查看送货", exact: true }).first().click();
  await page.getByRole("link", { name: "打开打印页", exact: true }).waitFor();
  assert.match(await page.locator(".delivery-detail").innerText(), /0\.125/);
  assert.equal((await (await context.request.get(`${base}/api/v1/deliveries/${activeDelivery.id}`)).json()).status, "active");
  assert.equal((await (await context.request.get(`${base}/api/v1/deliveries`)).json()).items.length, 2);
  checks.push("active_and_void_delivery_ledger_survives_database_restart_and_backup_restore");
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("heading", { name: "登录交有数", exact: true }).waitFor();
  checks.push("consistent_backup_restores_into_new_database_objects_and_local_login");

  const unexpectedHttp = httpErrors.filter(e => !(e.status === 401 && e.path === "/api/v1/auth/session") && !(e.status === 401 && e.fault && e.path === "/api/v1/orders/preview") && !(e.status === 422 && e.path === "/api/v1/orders/preview"));
  const unexpectedConsole = consoleErrors.filter(e => !e.fault && !(/(?:401|422)/.test(e.text) && /\/api\/v1\/(auth\/session|orders\/preview)$/.test(e.url)));
  assert.deepEqual(unexpectedHttp, []); assert.deepEqual(unexpectedConsole, []);
  assert.deepEqual(pageErrors, []); assert.deepEqual(externalRequests, []);
  assert.ok(logs.every(log => !log.text.includes("OFFLINE_UNEXPECTED_EGRESS:")));
  checks.push("zero_unexpected_external_requests_framework_overlays_or_runtime_errors");
} catch (error) {
  failed = String(error.stack ?? error);
  if (page) {
    try { await page.screenshot({ path: path.join(evidence, "failure.png"), fullPage: true }); } catch { /* preserve primary error */ }
  }
} finally {
  try { await browser?.close(); } catch (error) { failed ??= `Browser cleanup: ${error.message}`; }
  try { await stopServer(); } catch (error) { failed ??= `Application cleanup: ${error.message}`; }
  try { await helper("stop"); } catch (error) { failed ??= `Synthetic database cleanup: ${error.message}`; }
}

const hashes = {};
for (const relative of ["scripts/business-smoke.mjs", "scripts/business-smoke-env.py", "scripts/offline-smoke-server.py", "apps/web/dist/index.html", "contracts/openapi.json", "uv.lock", "package-lock.json"]) {
  hashes[relative] = createHash("sha256").update(await readFile(path.join(root, relative))).digest("hex");
}
const result = { status: failed ? "FAIL" : "PASS_ORDER_DELIVERY_LOCAL", at: new Date().toISOString(), base, checks, hashes,
  externalRequests, pageErrors, httpErrors, consoleErrors,
  limits: "Prepared environment and application-level egress controls; PostgreSQL restricted to loopback. Not OS network isolation, empty-machine installation, factory hardware or production acceptance.",
  ...(failed ? { failure: failed } : {}), evidence };
await writeFile(path.join(evidence, "result.json"), JSON.stringify(result, null, 2) + "\n");
await writeFile(path.join(evidence, "server.log"), logs.map(log => log.text).join("\n--- application restart ---\n"));
console.log(JSON.stringify({ status: result.status, checks, evidence, ...(failed ? { failure: failed } : {}) }, null, 2));
process.exitCode = failed ? 1 : 0;
