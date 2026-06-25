#!/usr/bin/env node
/**
 * Compile all shared JSON Schemas (draft 2020-12) including cross-file $refs.
 * Used by CI instead of ajv-cli validate, which requires instance data (-d).
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const schemaDir = fileURLToPath(new URL("../shared/jsonschema/v1/", import.meta.url));
const schemaPath = (name) => join(schemaDir, name);

const ajv = new Ajv2020({
  strict: false,
  allErrors: true,
  validateFormats: false,
});
addFormats(ajv);

const files = readdirSync(schemaDir)
  .filter((name) => name.endsWith(".json"))
  .sort();

const schemas = files.map((file) => JSON.parse(readFileSync(schemaPath(file), "utf8")));

for (const schema of schemas) {
  ajv.addSchema(schema);
}

let failed = false;
for (const schema of schemas) {
  const label = schema.$id?.split("/").pop() ?? "unknown";
  try {
    ajv.compile(schema);
    console.log(`OK  ${label}`);
  } catch (err) {
    failed = true;
    const message = err instanceof Error ? err.message : String(err);
    console.error(`FAIL ${label}: ${message}`);
  }
}

if (failed) {
  process.exit(1);
}
