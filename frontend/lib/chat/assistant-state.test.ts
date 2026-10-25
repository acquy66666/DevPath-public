// node --test lib/chat/assistant-state.test.ts  (npm test runs every *.test.ts)
//
// Naomi in the assistant's header (reaction map, design doc §5): thinking
// while an answer is looked up and written, holding her book once it cites
// the course, at rest otherwise. And the refusal rule, which must say exactly
// what the backend says.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { assistantHeader, isRefusal, readingChips, REFUSAL_MARK } from "./assistant-state.ts";

const backend = readFileSync(new URL("../../../backend/app/services/chat.py", import.meta.url), "utf8");

// The two refusals of the 22/09 demo and an answer of the same day
// (docs/report/assets/phase-4/chatbot-demo.txt).
const REFUSAL =
  "Nội dung này nằm ngoài phạm vi tài liệu của khóa học. Bạn có thể hỏi về các chủ đề có trong khóa học như vòng lặp, kiểu dữ liệu, hàm, hoặc biến trong Python nhé!";
const POLITE_REFUSAL = "Xin lỗi bạn, nội dung này nằm ngoài phạm vi tài liệu của khóa học.";
const ANSWER = "Theo tài liệu khóa học, `range(1, 10, 2)` có thêm bước nhảy 2, sinh ra các số: 1, 3, 5, 7, 9 [1].";

test("the refusal mark is the backend's", () => {
  assert.match(backend, new RegExp(`_REFUSAL_MARK = "${REFUSAL_MARK}"`));
  const opening = backend.match(/REFUSAL_OPENING = "([^"]+)"/)?.[1];
  assert.ok(opening, "REFUSAL_OPENING is still in chat.py");
  assert.ok(isRefusal(opening), "the opening the prompt asks for counts as a refusal");
});

test("a refusal is told by its first sentence only", () => {
  assert.equal(isRefusal(REFUSAL), true);
  assert.equal(isRefusal(POLITE_REFUSAL), true);
  assert.equal(isRefusal(ANSWER), false);
  assert.equal(
    isRefusal("Toán tử `=` gán giá trị [1]. Còn `==` thì nằm ngoài phạm vi tài liệu của khóa học."),
    false,
    "an answer that declines half of a question is still an answer",
  );
});

test("Naomi thinks while the answer is looked up and written", () => {
  assert.deepEqual(assistantHeader({ live: { phase: "searching", sources: 0 }, lastAnswer: null }), {
    mood: "thinking",
    status: "Đang tra cứu tài liệu khóa học…",
  });
  assert.deepEqual(assistantHeader({ live: { phase: "writing", sources: 6 }, lastAnswer: null }), {
    mood: "thinking",
    status: "Đang soạn câu trả lời từ 6 bài…",
  });
  assert.equal(assistantHeader({ live: { phase: "writing", sources: 0 }, lastAnswer: null }).status, "Đang soạn câu trả lời…");
});

test("an answer that cites the course: Naomi holds her book", () => {
  const header = assistantHeader({ live: null, lastAnswer: { id: "m1", content: ANSWER, citations: 1 } });
  assert.deepEqual(header, { mood: "answer", status: "Đã trả lời · 1 nguồn trong khóa học" });
});

test("nothing asked, a refusal, a stop or a failure: Naomi at rest", () => {
  assert.equal(assistantHeader({ live: null, lastAnswer: null }).mood, "rest");
  assert.deepEqual(assistantHeader({ live: null, lastAnswer: { id: "m2", content: REFUSAL, citations: 0 } }), {
    mood: "rest",
    status: "Câu vừa rồi nằm ngoài khóa học",
  });
  const answered = { id: "m1", content: ANSWER, citations: 1 };
  assert.equal(assistantHeader({ live: { phase: "stopped", sources: 2 }, lastAnswer: answered }).mood, "rest");
  assert.equal(assistantHeader({ live: { phase: "failed", sources: 0 }, lastAnswer: answered }).mood, "rest");
});

test("the lessons being read: three by name, the rest as a count", () => {
  const six = ["Ép kiểu", "Đọc hiểu thông báo lỗi", "Hello, World!", "f-string", "for và range", "while"];
  assert.deepEqual(readingChips(six), { titles: six.slice(0, 3), more: 3 });
  assert.deepEqual(readingChips(six.slice(0, 2)), { titles: six.slice(0, 2), more: 0 });
});
