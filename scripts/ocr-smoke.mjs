// Real native OCR + browser + database recovery, using an owned synthetic cluster only.
import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { once } from "node:events";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.FACTORYFLOW_PLAYWRIGHT_PATH ?? "playwright");
const python = path.join(root, ".venv/Scripts/python.exe");
const evidence = await mkdtemp(path.join(os.tmpdir(), "factoryflow-business-"));
const execute = async (...args) => (await promisify(execFile)(python, args, { cwd: root, windowsHide: true, timeout: 120000 })).stdout.trim();
const helper = action => execute("scripts/business-smoke-env.py", action, "--root", evidence);
const listener = net.createServer();
listener.listen(0, "127.0.0.1"); await once(listener, "listening");
const port = listener.address().port;
await new Promise(resolve => listener.close(resolve));
const base = `http://127.0.0.1:${port}`;
let server, browser, context, page, credentials, failure, pngSource, pdfSource, pngRun, pdfRun, confirmed;
let serverLog = "";
const checks = [], unexpectedNetwork = [], errors = [];

async function start(config = "app.json") {
  server = spawn(python, ["scripts/offline-smoke-server.py", "--config", path.join(evidence, config), "--port", String(port)], { cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  server.stdout.on("data", data => { serverLog += data.toString(); });
  server.stderr.on("data", data => { serverLog += data.toString(); });
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error("Synthetic server exited before readiness");
    try { if ((await fetch(`${base}/api/v1/health/ready`)).ok) return; } catch { /* waiting for owned listener */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error("Readiness timeout");
}
async function stop() {
  if (!server || server.exitCode !== null) return;
  const closed = once(server, "exit"); server.kill(); await closed;
}
async function login() {
  page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  page.on("dialog", dialog => dialog.accept());
  await page.goto(base);
  await page.getByLabel("账号", { exact: true }).fill(credentials.username);
  await page.getByLabel("密码", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("heading", { name: "目前没有待交明细" }).waitFor().catch(async () => {
    await page.getByRole("button", { name: "文件录入", exact: true }).waitFor();
  });
}
const count = async () => JSON.parse(await helper("inspect"));
async function json(url) { const response = await context.request.get(`${base}${url}`); assert.equal(response.status(), 200); return response.json(); }
async function upload(name) {
  await page.getByRole("button", { name: "文件录入", exact: true }).click();
  await page.getByLabel("订单文件").setInputFiles(path.join(evidence, name));
  const response = page.waitForResponse(r => r.url() === `${base}/api/v1/sources` && r.request().method() === "POST");
  await page.getByRole("button", { name: "上传并识别", exact: true }).click();
  assert.equal((await response).status(), 200);
  console.log(`Uploaded synthetic input: ${name}`);
  return (await json("/api/v1/sources")).items.find(item => item.filename === name).source_id;
}
async function snapshot(name) {
  await page.screenshot({ path: path.join(evidence, name), fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
}

try {
  await helper("prepare");
  await execute("scripts/ocr-smoke-fixtures.py", evidence);
  credentials = JSON.parse(await readFile(path.join(evidence, "client.json"), "utf8"));
  await start();
  browser = await chromium.launch({ channel: "chrome", headless: true,
    proxy: { server: "http://127.0.0.1:9", bypass: "127.0.0.1" }, args: ["--disable-background-networking"] });
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: "block" });
  context.setDefaultTimeout(15000);
  await context.route("**/*", async route => {
    if (new URL(route.request().url()).origin !== base) { unexpectedNetwork.push(route.request().url()); await route.abort(); }
    else await route.continue();
  });
  await login();
  await page.getByRole("button", { name: "客户", exact: true }).click();
  await page.getByLabel("客户完整名称").fill("Synthetic OCR Customer");
  await page.getByRole("button", { name: "创建客户", exact: true }).click();
  await page.getByText("Synthetic OCR Customer", { exact: true }).waitFor();
  pngSource = await upload("synthetic.png");
  await page.getByRole("heading", { name: "录入订单", exact: true }).waitFor({ timeout: 110000 });
  assert.equal(await page.getByLabel("客户", { exact: true }).inputValue(), "");
  assert.equal((await count()).orders, 0);
  const picture = page.getByRole("img", { name: "原件第 1 页，点击放大" });
  await picture.waitFor();
  await picture.evaluate(img => img.decode());
  await snapshot("ocr-candidate-desktop.png");
  checks.push("real_png_native_ocr_original_preview_candidate_and_no_automatic_order");
  await page.getByLabel("客户", { exact: true }).selectOption({ label: "Synthetic OCR Customer" });
  await page.getByLabel("客户订单号", { exact: true }).fill("SYN-HUMAN-CORRECTED");
  await page.getByLabel("订单日期", { exact: true }).fill("2026-10-02");
  await page.getByLabel("币种", { exact: true }).selectOption("CNY");
  assert.equal(await page.locator("fieldset.entry-line").count(), 2);
  for (const [index, quantity] of ["1.125", "2.000"].entries()) {
    const line = page.getByRole("group", { name: `第 ${index + 1} 行`, exact: true });
    await line.getByLabel("数量", { exact: true }).fill(quantity);
    await line.getByLabel("单位", { exact: true }).fill(index ? "PCS" : "KG");
  }
  await page.getByRole("button", { name: "核对订单", exact: true }).click();
  await page.getByRole("heading", { name: "核对订单", exact: true }).waitFor();
  await snapshot("ocr-review-desktop.png");
  let lost = false;
  await context.route("**/api/v1/orders", async route => {
    if (route.request().method() === "POST" && !lost) {
      lost = true; const response = await route.fetch(); assert.equal(response.status(), 200);
      confirmed = await response.json(); await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认生成订单", exact: true }).click();
  await page.getByRole("button", { name: "重试本次提交", exact: true }).click();
  await page.getByRole("heading", { name: "SYN-HUMAN-CORRECTED", exact: true }).waitFor();
  assert.equal((await count()).orders, 1);
  const revision = await json(`/api/v1/documents/${confirmed.revision_id}`);
  assert.equal(revision.content.schema_version, 3);
  assert.equal(revision.content.order.lines[0].source_quantity_text, "1.125");
  assert.equal(revision.content.order.lines[1].source_quantity_text, "2.000");
  assert.equal(revision.content.order.lines[0].source_unit_price, null);
  pngRun = revision.content.source.extraction_id;
  const download = await context.request.get(`${base}/api/v1/sources/${pngSource}/download`);
  assert.deepEqual(await download.body(), await readFile(path.join(evidence, "synthetic.png")));
  assert.equal(createHash("sha256").update(await download.body()).digest("hex"), revision.content.source.original_sha256);
  await page.getByRole("button", { name: "查看确认内容", exact: true }).click();
  await page.getByRole("heading", { name: "原件对照", exact: true }).waitFor();
  checks.push("human_corrected_confirmation_replays_after_lost_response_and_retains_exact_original");

  let extractionLost = false;
  await context.route("**/api/v1/sources/*/extractions", async route => {
    if (!extractionLost) { extractionLost = true; const response = await route.fetch(); assert.equal(response.status(), 200); pdfRun = (await response.json()).extraction_id; await route.abort("failed"); }
    else await route.continue();
  });
  pdfSource = await upload("synthetic-two-pages.pdf");
  await page.getByRole("button", { name: "重试本次识别", exact: true }).click({ timeout: 110000 });
  await page.getByRole("heading", { name: "录入订单", exact: true }).waitFor();
  assert.equal((await count()).extraction_runs, 2);
  const pdf = await json(`/api/v1/extractions/${pdfRun}`);
  assert.equal(pdf.pages.length, 2); assert.equal(pdf.status, "ready");
  await page.getByLabel("原件页码").selectOption("2");
  await page.getByRole("img", { name: "原件第 2 页，点击放大" }).evaluate(img => img.decode());
  await page.setViewportSize({ width: 390, height: 844 });
  await snapshot("ocr-pdf-mobile.png");
  await page.getByRole("button", { name: "返回订单", exact: true }).click();
  checks.push("real_two_page_pdf_and_extraction_response_loss_replay_with_mobile_review");

  await stop(); await helper("restart-database"); await start();
  assert.equal((await json(`/api/v1/extractions/${pdfRun}`)).pages.length, 2);
  assert.equal((await json(`/api/v1/documents/${confirmed.revision_id}`)).sha256, confirmed.sha256);
  checks.push("pending_and_confirmed_sources_survive_database_and_api_restart");
  const restored = JSON.parse(await helper("restore-check"));
  assert.equal(restored.backup_objects, 5);
  await stop(); await start("app-restored.json");
  await context.clearCookies(); await page.close(); await login();
  const list = await json("/api/v1/sources");
  assert.equal(list.items.length, 2);
  assert.equal(list.items.find(item => item.source_id === pngSource).order_id, confirmed.order_id);
  assert.equal(list.items.find(item => item.source_id === pdfSource).order_id, null);
  assert.equal((await json(`/api/v1/extractions/${pngRun}`)).trace_hash, revision.content.source.trace_hash);
  assert.equal((await json(`/api/v1/extractions/${pdfRun}`)).pages.length, 2);
  const restoredOriginal = await context.request.get(`${base}/api/v1/sources/${pdfSource}/download`);
  assert.deepEqual(await restoredOriginal.body(), await readFile(path.join(evidence, "synthetic-two-pages.pdf")));
  checks.push("backup_restores_pending_pdf_confirmed_source_trace_hashes_and_local_login");
  assert.deepEqual(unexpectedNetwork, []); assert.deepEqual(errors, []);
  assert.match(serverLog, /OFFLINE_GUARD_READY:2_NEGATIVE_CONTROLS_BLOCKED/);
  assert.doesNotMatch(serverLog, /OFFLINE_UNEXPECTED_EGRESS/);
  checks.push("browser_and_python_guards_no_unexpected_egress_native_process_not_os_isolated");
} catch (error) {
  failure = error.stack ?? String(error);
  if (page) await page.screenshot({ path: path.join(evidence, "failure.png"), fullPage: true }).catch(() => {});
} finally {
  await browser?.close(); await stop();
  await helper("stop").catch(error => { failure ??= error.message; });
  await writeFile(path.join(evidence, "result.json"), JSON.stringify({ status: failure ? "FAIL" : "PASS_LOCAL_OCR", checks, failure, unexpectedNetwork, errors }, null, 2));
  await writeFile(path.join(evidence, "server.log"), serverLog);
}
console.log(JSON.stringify({ status: failure ? "FAIL" : "PASS_LOCAL_OCR", evidence, checks, failure }, null, 2));
if (failure) process.exitCode = 1;
