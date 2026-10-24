import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../apps/web/src");
const dictionaryFile = fs.readFileSync(path.join(root, "messages.en.ts"), "utf8");
const dictionary = JSON.parse(dictionaryFile.slice(dictionaryFile.indexOf(" = ") + 3).trim().replace(/;$/, ""));
const placeholders = text => [...text.matchAll(/\{\d+\}/g)].map(match => match[0]).sort();
for (const [key, value] of Object.entries(dictionary)) {
  assert.deepEqual(placeholders(value), placeholders(key), `Translation placeholders: ${key}`);
}
const missing = [];
let calls = 0;
for (const file of fs.readdirSync(root, { recursive: true }).filter(file => /\.tsx?$/.test(file) && file !== "messages.en.ts")) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  function visit(node) {
    if (ts.isCallExpression(node) && ["t", "msg"].includes(node.expression.getText(tree)) && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) {
      const key = node.arguments[0].text;
      calls++;
      if (/[\u3400-\u9fff]/.test(key) && !Object.hasOwn(dictionary, key)) missing.push(`${file}:${tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1}: ${key}`);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
}
assert.deepEqual(missing, [], "Missing English product messages");
console.log(`Checked ${Object.keys(dictionary).length} translations and ${calls} literal message calls.`);
