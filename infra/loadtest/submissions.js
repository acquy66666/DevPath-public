// A class hitting one code exercise at the same moment.
//
//   k6 run -e STAGE=/stage/stage.json submissions.js     (README.md has the
//                                                         full docker command)
//
// STAGE is what `python -m scripts.stage_load_test` printed: a published
// exercise, and that many enrolled students with access tokens. The last
// student submits alone first (`mot-minh`), so the class is not timed against
// a cold sandbox and so there is a number for an empty queue. Then every other
// student submits at once (`lop-hoc`) -- per-vu-iterations starts all of them
// together -- and each waits for the verdict on the same WebSocket the
// exercise page opens, offering ["bearer", token] as subprotocols.
//
// What is timed is what the student sees: from pressing "Nộp bài" to the
// socket saying `done`. The split into queue wait and grading is what
// `scripts.bench_grading` measures from inside; this measures it from outside,
// through nginx, the production API and the production grading worker.
//
// BROWSE_VUS > 0 adds people browsing the catalogue for the length of the
// class, to see what grading costs everybody else on the same box.

import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";
import { Counter, Rate, Trend } from "k6/metrics";
import { WebSocket } from "k6/websockets";

import { BASE_URL, NAMES, summarize, visit } from "./catalogue.js";

const stage = JSON.parse(open(__ENV.STAGE || "/stage/stage.json"));
const WS_URL = BASE_URL.replace(/^http/, "ws");
const CLASS_SIZE = stage.students.length - 1;
const BROWSE_VUS = Number(__ENV.BROWSE_VUS || 0);
const CLASS_STARTS = "20s";
const GIVE_UP_MS = 180_000;

const toVerdict = new Trend("nop_den_verdict", true);
const accepted = new Rate("bai_dung");
const unfinished = new Counter("khong_xong");

const scenarios = {
  "mot-minh": {
    executor: "per-vu-iterations",
    vus: 1,
    iterations: 1,
    exec: "submit",
    maxDuration: "60s",
  },
  "lop-hoc": {
    executor: "per-vu-iterations",
    vus: CLASS_SIZE,
    iterations: 1,
    exec: "submit",
    startTime: CLASS_STARTS,
    maxDuration: "5m",
  },
};
if (BROWSE_VUS > 0) {
  // From a little before the class submits until well after the last verdict.
  scenarios.duyet = {
    executor: "constant-vus",
    vus: BROWSE_VUS,
    duration: __ENV.BROWSE_DURATION || "150s",
    startTime: "10s",
    exec: "visit",
  };
}

export const options = {
  insecureSkipTLSVerify: __ENV.INSECURE_TLS === "1",
  scenarios,
  thresholds: {
    bai_dung: ["rate==1"],
    khong_xong: ["count==0"],
    "nop_den_verdict{scenario:mot-minh}": ["max<30000"],
    "nop_den_verdict{scenario:lop-hoc}": ["max<180000"],
    "http_req_duration{name:nop-bai}": ["p(95)<1000"],
    ...(BROWSE_VUS > 0
      ? {
          [`http_req_duration{name:${NAMES.page}}`]: ["p(95)<2000"],
          [`http_req_duration{name:${NAMES.api}}`]: ["p(95)<500"],
          [`http_req_duration{name:${NAMES.pageSearch}}`]: ["p(95)<2000"],
          [`http_req_duration{name:${NAMES.apiSearch}}`]: ["p(95)<500"],
        }
      : {}),
  },
  summaryTrendStats: ["count", "avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export { visit };

export function submit() {
  const alone = exec.scenario.name === "mot-minh";
  // The warm-up takes the last student; the class takes the rest, one each.
  const student = alone
    ? stage.students[CLASS_SIZE]
    : stage.students[exec.scenario.iterationInTest];

  const pressed = Date.now();
  const response = http.post(
    `${BASE_URL}/api/v1/code-exercises/${stage.exercise_id}/submissions`,
    JSON.stringify({ code: stage.solution }),
    {
      headers: {
        Authorization: `Bearer ${student.token}`,
        "Content-Type": "application/json",
      },
      tags: { name: "nop-bai" },
    },
  );
  const sent = check(response, { "nộp bài: 201": (r) => r.status === 201 });
  if (!sent) {
    console.error(`${student.email}: ${response.status} ${response.body}`);
    unfinished.add(1);
    return;
  }
  const submissionId = response.json("id");

  const socket = new WebSocket(`${WS_URL}/api/v1/submissions/${submissionId}/events`, [
    "bearer",
    student.token,
  ]);
  let finished = false;
  const giveUp = setTimeout(() => {
    if (!finished) {
      console.error(`${student.email}: không có verdict sau ${GIVE_UP_MS / 1000}s`);
      unfinished.add(1);
      socket.close();
    }
  }, GIVE_UP_MS);

  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.status !== "done" && event.status !== "error") return;
    finished = true;
    clearTimeout(giveUp);
    toVerdict.add(Date.now() - pressed);
    accepted.add(event.status === "done" && event.verdict === "AC");
    if (event.verdict !== "AC") {
      console.error(`${student.email}: ${event.status} ${event.verdict}`);
    }
    socket.close();
  };
  socket.onerror = (error) => {
    if (finished) return;
    finished = true;
    clearTimeout(giveUp);
    console.error(`${student.email}: websocket ${error.error}`);
    unfinished.add(1);
  };
}

export function handleSummary(data) {
  const label = BROWSE_VUS > 0 ? `lop-hoc-${CLASS_SIZE}-duyet-${BROWSE_VUS}vu` : `lop-hoc-${CLASS_SIZE}`;
  return summarize(data, label);
}
