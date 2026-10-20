// node --test lib/api/filename.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import { filenameFrom } from "./filename.ts";

test("the UTF-8 name wins over the ASCII fallback", () => {
  const header =
    "attachment; filename=\"devpath_bang-ke.xlsx\"; filename*=UTF-8''devpath_b%E1%BA%A3ng-k%C3%AA.xlsx";
  assert.equal(filenameFrom(header, "x.xlsx"), "devpath_bảng-kê.xlsx");
});

test("a plain name is read when there is no UTF-8 one", () => {
  assert.equal(filenameFrom('attachment; filename="bao-cao.xlsx"', "x.xlsx"), "bao-cao.xlsx");
});

test("no header, or a malformed one, falls back", () => {
  assert.equal(filenameFrom(null, "x.xlsx"), "x.xlsx");
  assert.equal(filenameFrom("attachment; filename*=UTF-8''%E1%ZZ", "x.xlsx"), "x.xlsx");
});
