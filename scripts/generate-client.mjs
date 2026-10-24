import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const schema = new URL("../contracts/openapi.json", import.meta.url);
const target = new URL("../packages/api-client/src/schema.d.ts", import.meta.url);
const source = "/** Generated from contracts/openapi.json. Do not edit. */\n" +
  astToString(await openapiTS(schema));

if (process.argv.includes("--check")) {
  const current = await readFile(target, "utf8").catch(() => "");
  if (current !== source) {
    console.error("API type drift: run npm run contracts:generate");
    process.exitCode = 1;
  } else {
    console.log("API types match OpenAPI.");
  }
} else {
  await writeFile(target, source, "utf8");
  console.log("Generated packages/api-client/src/schema.d.ts");
}
