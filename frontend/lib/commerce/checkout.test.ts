// node --test lib/commerce/checkout.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import { nothingToPay, settledOrderPath } from "./checkout.ts";

test("an order that comes back paid goes to our own result page", () => {
  assert.equal(
    settledOrderPath({ code: "DP261016ABCDEF", status: "paid" }),
    "/thanh-toan/ket-qua?ma=DP261016ABCDEF",
  );
});

test("an order still waiting for money goes to the gateway", () => {
  assert.equal(settledOrderPath({ code: "DP261016ABCDEF", status: "pending" }), null);
});

test("the code is a query value, encoded as one", () => {
  assert.equal(
    settledOrderPath({ code: "DP 1&x=2", status: "paid" }),
    "/thanh-toan/ket-qua?ma=DP%201%26x%3D2",
  );
});

test("only exactly zero is nothing to pay", () => {
  assert.equal(nothingToPay("0.00"), true);
  assert.equal(nothingToPay("0"), true);
  assert.equal(nothingToPay("1.00"), false);
  assert.equal(nothingToPay("399000.00"), false);
  // A number the API did not send is not a reason to skip the gateway.
  assert.equal(nothingToPay("không phải số"), false);
});
