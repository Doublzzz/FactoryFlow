import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { build } from "vite";

// Execute the actual shared UI factory, using the existing TSX build pipeline.
// Both quick collection and the editable collection form use this factory.
const built = await build({
  configFile: false,
  logLevel: "silent",
  build: {
    lib: { entry: fileURLToPath(new URL("../apps/web/src/components/MaterialSelect.tsx", import.meta.url)), formats: ["es"] },
    write: false,
    minify: false,
  },
});
const output = Array.isArray(built) ? built[0] : built;
const code = output.output.find(item => item.type === "chunk" && item.isEntry).code;
const { materialFromOrderLine } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("order collection sends only OrderNewMaterial fields, without the catalog-only kind", () => {
  const line = { item_name: "Synthetic bracket", description: "Source description", specification: "S-1", source_unit: "PCS" };
  assert.deepEqual(materialFromOrderLine(line), {
    name: "Synthetic bracket", own_code: "", specification: "S-1", unit: "PCS",
  });
  assert.equal(line.description, "Source description");
});

test("order collection preserves missing unit and falls back to the source description", () => {
  assert.deepEqual(materialFromOrderLine({ item_name: null, description: "Synthetic source item", specification: null, source_unit: null }), {
    name: "Synthetic source item", own_code: "", specification: null, unit: null,
  });
});
