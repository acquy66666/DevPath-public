// node --test lib/auth/next-path.test.ts  (npm test runs every *.test.ts)
//
// Node runs this file as TypeScript by stripping the types, with no test
// framework to install. It is left out of tsconfig so `next build` does not
// type-check an import ending in `.ts`, which Node needs and the bundler
// configuration refuses.
import assert from "node:assert/strict";
import { test } from "node:test";

import { safeNextPath } from "./next-path.ts";

test("an ordinary path on this site goes through as it is", () => {
  assert.equal(safeNextPath("/khoa-hoc/python-co-ban"), "/khoa-hoc/python-co-ban");
  assert.equal(safeNextPath("/thanh-toan/ket-qua?ma=DP2610016ABCDE"), "/thanh-toan/ket-qua?ma=DP2610016ABCDE");
  assert.equal(safeNextPath("/hoc/python?bai=1#ghi-chu"), "/hoc/python?bai=1#ghi-chu");
});

test("nothing, or not a path, goes home", () => {
  assert.equal(safeNextPath(undefined), "/");
  assert.equal(safeNextPath(""), "/");
  assert.equal(safeNextPath("khoa-hoc"), "/");
  assert.equal(safeNextPath("https://evil.example/dang-nhap"), "/");
  assert.equal(safeNextPath("javascript:alert(1)"), "/");
});

test("a path that the browser reads as another host goes home", () => {
  // Each of these starts with "/" and not with "//", which is all the first
  // version of the guard looked at -- and each one, resolved against the
  // page, lands on evil.example. A backslash counts as a slash in an http
  // URL, and tabs and newlines are dropped before parsing.
  for (const sneaky of [
    "//evil.example",
    "/\\evil.example",
    "/\\/evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
    "\\\\evil.example",
  ]) {
    assert.equal(safeNextPath(sneaky), "/", JSON.stringify(sneaky));
  }
});

test("only the first of a repeated parameter is read", () => {
  assert.equal(safeNextPath(["/khoa-hoc", "//evil.example"]), "/khoa-hoc");
  assert.equal(safeNextPath(["//evil.example", "/khoa-hoc"]), "/");
});
