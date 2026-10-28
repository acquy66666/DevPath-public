// node --test lib/admin/admin-view.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  attentionCards,
  badgeCount,
  LONG_WAIT_DAYS,
  PLACE_GROUPS,
  PLACES,
  placeOf,
  waitedDays,
  waitingTotal,
  waitLabel,
} from "./admin-view.ts";

const summary = { pending_courses: 2, pending_reports: 1, locked_users: 1 };

test("every admin route is one place in one group", () => {
  assert.equal(PLACES.length, 12);
  assert.equal(new Set(PLACES.map((p) => p.href)).size, 12);
  assert.deepEqual(
    PLACE_GROUPS.map((g) => g.label),
    [null, "Kiểm duyệt", "Tài chính", "Nội dung sàn"],
  );
});

test("a path belongs to its own place or the one it sits under", () => {
  assert.equal(placeOf("/quan-tri").href, "/quan-tri");
  assert.equal(placeOf("/quan-tri/").href, "/quan-tri");
  assert.equal(placeOf("/quan-tri/khoa-hoc").href, "/quan-tri/khoa-hoc");
  assert.equal(placeOf("/quan-tri/khoa-hoc/abc").href, "/quan-tri/khoa-hoc");
  assert.equal(placeOf("/quan-tri/thanh-toan/123").href, "/quan-tri/thanh-toan");
  // A prefix of a word is not a parent.
  assert.equal(placeOf("/quan-tri/banner-cu").href, "/quan-tri");
});

test("badges count the queues, and only the queues", () => {
  const counts = PLACES.map((p) => badgeCount(p, summary)).filter((n) => n > 0);
  assert.deepEqual(counts, [2, 1]);
  assert.equal(badgeCount(PLACES[1], undefined), 0);
  assert.equal(waitingTotal(summary), 3);
  assert.equal(waitingTotal(undefined), 0);
});

test("waiting is counted in whole days, from the moment the course was sent", () => {
  const now = new Date("2026-10-29T10:00:00+07:00");
  assert.equal(waitedDays("2026-10-29T09:00:00+07:00", now), 0);
  assert.equal(waitedDays("2026-10-26T10:00:00+07:00", now), 3);
  assert.equal(waitedDays("2026-10-26T10:00:01+07:00", now), 2);
  assert.equal(waitedDays("2026-10-30T10:00:00+07:00", now), 0);
  assert.equal(LONG_WAIT_DAYS, 3);
  assert.equal(waitLabel(0), "chờ chưa tới 1 ngày");
  assert.equal(waitLabel(4), "chờ 4 ngày");
});

test("the overview names the oldest course, and says when nothing waits", () => {
  const cards = attentionCards(summary, { title: "Git từ số 0", days: 3 });
  assert.deepEqual(cards.map((c) => c.kind), ["courses", "reports", "locked"]);
  assert.equal(cards[0].detail, "Chờ lâu nhất: “Git từ số 0”, chờ 3 ngày");
  assert.equal(cards[2].quiet, true);

  const idle = attentionCards({ pending_courses: 0, pending_reports: 0, locked_users: 0 }, null);
  assert.equal(idle[0].detail, "Không có khóa học nào đang chờ");
  assert.equal(idle[1].detail, "Không có báo cáo nào đang chờ");
});
