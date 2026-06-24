import test from "node:test";
import assert from "node:assert/strict";
import { AegisPolicyBlockedError } from "../dist/errors.js";

test("AegisPolicyBlockedError carries layer", () => {
  const err = new AegisPolicyBlockedError("blocked", { layer: "input_defense" });
  assert.equal(err.layer, "input_defense");
  assert.equal(err.name, "AegisPolicyBlockedError");
});
