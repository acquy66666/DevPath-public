// node --test lib/commerce/commerce-view.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import { cartHeadline, payableCount, payLabel, payNote, wishlistPicks } from "./cart-view.ts";
import { FRESH_FOR_MS, orderHeadline, orderSeenKey, shouldReact } from "./order-view.ts";

const line = (id: string, owned = false) => ({ course: { id }, already_enrolled: owned });

test("the cart headline counts lines and says which ones are free of charge", () => {
  assert.equal(cartHeadline([line("a"), line("b")]), "2 khóa học");
  assert.equal(
    cartHeadline([line("a"), line("b"), line("c"), line("d", true)]),
    "4 khóa học · 1 khóa bạn đã có không bị tính tiền",
  );
  assert.equal(cartHeadline([line("a", true)]), "1 khóa học · bạn đều đã có, không có gì để trả");
  assert.equal(payableCount([line("a"), line("b", true)]), 1);
});

test("the pay button says what it costs, or that nothing does", () => {
  assert.equal(payLabel("598500.00", "598.500 ₫"), "Thanh toán 598.500 ₫ qua VNPay");
  assert.equal(payLabel("0.00", "0 ₫"), "Nhận khóa học");
  assert.match(payNote("598500.00"), /VNPay/);
  assert.match(payNote("0"), /^Đơn 0đ/);
});

test("wishlist picks skip what is in the cart, already owned, or free", () => {
  const saved = [
    { course: { id: "ts", price: "299000.00" } },
    { course: { id: "dsa", price: "499000.00" } },
    { course: { id: "free", price: "0.00" } },
    { course: { id: "docker", price: "399000.00" } },
    { course: { id: "oop", price: "199000.00" } },
  ];
  const picks = wishlistPicks(saved, [line("dsa")]);
  assert.deepEqual(picks.map((item) => item.course.id), ["ts", "docker"]);
  assert.equal(wishlistPicks(saved, [], new Set(), 10).length, 4);
  // Bought since it was saved: the wishlist still holds it, the picks do not.
  assert.deepEqual(
    wishlistPicks(saved, [line("dsa")], new Set(["ts"])).map((item) => item.course.id),
    ["docker", "oop"],
  );
});

const facts = {
  status: "paid" as const,
  free: false,
  itemCount: 3,
  failureCode: null,
  waiting: false,
};

test("a paid order celebrates with paid and counts the courses", () => {
  const head = orderHeadline(facts);
  assert.equal(head.mood, "paid");
  assert.equal(head.title, "Thanh toán thành công");
  assert.match(head.description, /^3 khóa học đã vào tài khoản/);
  assert.match(orderHeadline({ ...facts, itemCount: 1 }).description, /^Khóa học đã vào/);
  assert.equal(orderHeadline({ ...facts, free: true }).title, "Đã nhận khóa học");
});

test("a failed order says why in words, and that nothing was charged", () => {
  const head = orderHeadline({ ...facts, status: "failed", failureCode: "24" });
  assert.equal(head.mood, "oops");
  assert.equal(head.description, "Bạn đã hủy giao dịch trên trang của VNPay.");
  assert.match(head.reassurance ?? "", /Chưa có khoản nào bị trừ/);
  // A code we have no words for still gets a sentence, never the bare number.
  const unknown = orderHeadline({ ...facts, status: "failed", failureCode: "99" });
  assert.doesNotMatch(unknown.description, /99/);
});

test("waiting has no Naomi, and says something else once the page stops asking", () => {
  const waiting = orderHeadline({ ...facts, status: "pending", waiting: true });
  const gaveUp = orderHeadline({ ...facts, status: "pending", waiting: false });
  assert.equal(waiting.mood, null);
  assert.equal(gaveUp.mood, null);
  assert.notEqual(waiting.title, gaveUp.title);
  assert.equal(orderHeadline({ ...facts, status: "cancelled" }).mood, "oops");
});

test("Naomi reacts once per outcome, and only to a fresh order", () => {
  const now = Date.parse("2026-10-27T08:00:00Z");
  const placed = "2026-10-27T07:55:00Z";
  assert.equal(shouldReact("paid", null, placed, now), true);
  assert.equal(shouldReact("paid", "paid", placed, now), false);
  // Seen while pending, now paid: that is news.
  assert.equal(shouldReact("paid", "pending", placed, now), true);
  assert.equal(shouldReact("failed", null, placed, now), true);
  assert.equal(shouldReact("pending", null, placed, now), false);
  assert.equal(shouldReact("cancelled", null, placed, now), false);
  const old = new Date(now - FRESH_FOR_MS - 1).toISOString();
  assert.equal(shouldReact("paid", null, old, now), false);
  assert.equal(orderSeenKey("DP1"), "devpath:order-seen:DP1");
});
