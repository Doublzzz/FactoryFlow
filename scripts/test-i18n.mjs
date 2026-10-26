import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

let sequence = 0;
async function load() {
  const compile = source => ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
  const uri = code => `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`;
  const dictionary = uri(compile(await readFile(new URL("../apps/web/src/messages.en.ts", import.meta.url), "utf8")));
  const source = await readFile(new URL("../apps/web/src/i18n.ts", import.meta.url), "utf8");
  return import(uri(compile(source).replace('"./messages.en"', JSON.stringify(dictionary)) + `\n// instance ${++sequence}`));
}

test("language changes labels but never translates interpolated business text", async () => {
  const { t, msg, setLocale } = await load();
  const saved = msg("第 {0} 行", ["客户名称 {1}"]);
  setLocale("en");
  assert.equal(t("客户名称"), "Customer name");
  assert.equal(t(saved), "Row 客户名称 {1}");
  setLocale("zh-CN");
  assert.equal(t(saved), "第 客户名称 {1} 行");
  assert.equal(t(msg("{0} / {1}", [msg("客户名称"), "客户名称"])), "客户名称 / 客户名称");
  setLocale("en");
  assert.equal(t(msg("{0} / {1}", [msg("客户名称"), "客户名称"])), "Customer name / 客户名称");
});

test("locale subscription keeps state in memory if browser storage is unavailable", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("blocked"); } });
  try {
    const { getLocale, setLocale, subscribeLocale } = await load();
    assert.equal(getLocale(), "zh-CN");
    let changes = 0;
    const unsubscribe = subscribeLocale(() => changes++);
    setLocale("en");
    setLocale("en");
    assert.equal(getLocale(), "en");
    assert.equal(changes, 1);
    unsubscribe();
    setLocale("zh-CN");
    assert.equal(changes, 1);
    assert.throws(() => setLocale("fr"), /locale/);
    assert.equal(getLocale(), "zh-CN");
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
    else delete globalThis.localStorage;
  }
});

test("browser preference persists and invalid stored values use Chinese", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const values = new Map();
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } });
  try {
    (await load()).setLocale("en");
    assert.equal((await load()).getLocale(), "en");
    values.set("factoryflow.locale", "fr");
    assert.equal((await load()).getLocale(), "zh-CN");
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
    else delete globalThis.localStorage;
  }
});

test("English launcher explicitly selects English without changing the default", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "location");
  Object.defineProperty(globalThis, "location", { configurable: true, value: { search: "?lang=en" } });
  try {
    assert.equal((await load()).getLocale(), "en");
    globalThis.location.search = "?lang=unknown";
    assert.equal((await load()).getLocale(), "zh-CN");
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "location", descriptor);
    else delete globalThis.location;
  }
});
