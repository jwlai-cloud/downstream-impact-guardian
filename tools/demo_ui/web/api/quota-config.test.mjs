// Guards the DEMO_MAX_RUNS_PER_DAY parsing in create-demo.js. Both naive
// readings of that variable fail OPEN (NaN disables the cap; `|| 40` turns an
// explicit 0 into 40), and it is the only control bounding cost when
// DEMO_GATE=off -- so the parsing rule gets a test even though it is small.
//
//   node --test tools/demo_ui/web/api/quota-config.test.mjs
//
// Mirrors create-demo.js. Kept as a copy rather than an import because
// tools/demo_ui/web/ has no package.json and adding {"type":"module"} purely
// for testability would change how Vercel builds the deployed functions.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function parseCap(raw) {
  const cap = raw === undefined || raw.trim() === "" ? 40 : Number(raw);
  return { cap, valid: Number.isSafeInteger(cap) && cap >= 0 };
}

test("unset or blank uses the default", () => {
  for (const raw of [undefined, "", "   "]) {
    assert.deepEqual(parseCap(raw), { cap: 40, valid: true });
  }
});

test("an explicit 0 blocks everything and is not coerced to the default", () => {
  assert.deepEqual(parseCap("0"), { cap: 0, valid: true });
});

test("malformed values are invalid, so the endpoint fails closed", () => {
  for (const raw of ["fourty", "40abc", "-1", "1.5", "NaN", "Infinity"]) {
    assert.equal(parseCap(raw).valid, false, `${raw} must be rejected`);
  }
});

test("the caps a real deployment would set are accepted", () => {
  for (const raw of ["1", "15", "40", "500"]) {
    assert.equal(parseCap(raw).valid, true, `${raw} must be accepted`);
  }
});

// Fails if create-demo.js stops using the strict rule this file encodes.
test("create-demo.js still parses strictly and fails closed", () => {
  const src = readFileSync(new URL("./create-demo.js", import.meta.url), "utf8");
  assert.match(src, /Number\.isSafeInteger\(MAX_RUNS_PER_DAY\)/);
  assert.match(src, /MAX_RUNS_RAW\.trim\(\) === ""/);
  assert.match(src, /!MAX_RUNS_VALID/);
  assert.doesNotMatch(
    src,
    /Number\(process\.env\.DEMO_MAX_RUNS_PER_DAY \|\| 40\)/,
    "the fail-open `|| 40` form must not come back"
  );
});
