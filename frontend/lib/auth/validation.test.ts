import assert from "node:assert/strict";
import { test } from "node:test";

import { PASSWORD_MIN_LENGTH, passwordProgress, validatePassword } from "./validation.ts";

test("the rule line counts down to the minimum, then says it is met", () => {
  assert.deepEqual(passwordProgress(""), { met: false, tooLong: false, text: "Tối thiểu 8 ký tự" });
  assert.deepEqual(passwordProgress("hoc"), { met: false, tooLong: false, text: "Tối thiểu 8 ký tự · còn 5" });
  assert.deepEqual(passwordProgress("hoc-python"), { met: true, tooLong: false, text: "Tối thiểu 8 ký tự" });
});

test("the rule line and the submit check agree on every length", () => {
  for (let length = 0; length <= PASSWORD_MIN_LENGTH + 2; length += 1) {
    const value = "a".repeat(length);
    const progress = passwordProgress(value);
    assert.equal(progress.met, validatePassword(value) === null, `length ${length}`);
  }
});

test("too many bytes is said on the rule line, not only on submit", () => {
  const progress = passwordProgress("ữ".repeat(25)); // 3 bytes each, 75 > 72
  assert.equal(progress.met, false);
  assert.equal(progress.tooLong, true);
  assert.equal(validatePassword("ữ".repeat(25)) !== null, true);
});
