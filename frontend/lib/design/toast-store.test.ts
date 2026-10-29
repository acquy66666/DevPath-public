// node --test lib/design/toast-store.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import { createToastStore, MAX_TOASTS } from "./toast-store.ts";

test("a toast is shown open, with its own id", () => {
  const store = createToastStore();
  const a = store.show({ title: "Đã bỏ A khỏi giỏ hàng" });
  const b = store.show({ title: "Đã bỏ B khỏi giỏ hàng" });
  assert.notEqual(a, b);
  assert.deepEqual(
    store.snapshot().map((t) => [t.title, t.open]),
    [
      ["Đã bỏ A khỏi giỏ hàng", true],
      ["Đã bỏ B khỏi giỏ hàng", true],
    ],
  );
});

test("closing keeps the toast for its fade-out; removing takes it away", () => {
  const store = createToastStore();
  const id = store.show({ title: "x" });
  store.close(id);
  assert.equal(store.snapshot()[0].open, false);
  store.remove(id);
  assert.equal(store.snapshot().length, 0);
});

test(`at most ${MAX_TOASTS} are open: the oldest closes`, () => {
  const store = createToastStore();
  const ids = Array.from({ length: MAX_TOASTS + 2 }, (_, i) => store.show({ title: `t${i}` }));
  const open = store.snapshot().filter((t) => t.open).map((t) => t.id);
  assert.deepEqual(open, ids.slice(-MAX_TOASTS));
});

test("listeners hear every change and can leave", () => {
  const store = createToastStore();
  let heard = 0;
  const leave = store.subscribe(() => heard++);
  const id = store.show({ title: "x" });
  store.close(id);
  store.close(id); // already closed: nothing changes, nobody is told
  store.remove(id);
  leave();
  store.show({ title: "y" });
  assert.equal(heard, 3);
});

test("the snapshot only changes when the list does", () => {
  const store = createToastStore();
  const before = store.snapshot();
  store.close(42);
  store.remove(42);
  assert.equal(store.snapshot(), before);
});
