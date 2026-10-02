// The catalogue under load: people browsing the course list.
//
//   VUS=25 DURATION=60s k6 run catalogue.js        (see README.md for the
//                                                    docker command and setup)
//
// One virtual user is one person browsing: the list page, a search, page two
// of the list, with THINK seconds between pages. The pages are what a browser
// asks nginx for -- rendered by Next on the server, which in turn calls the
// API on the compose network. The API's own listing is asked through nginx
// too, on the same visit, so the report can say how much of a page's time is
// the API and how much is rendering.
//
// Static assets are left out on purpose: a browser fetches them once and nginx
// serves them from disk with a year-long cache header -- they are not what a
// second or a hundredth visitor costs.

import http from "k6/http";
import { check, sleep } from "k6";

export const BASE_URL = (__ENV.BASE_URL || "https://localhost").replace(/\/$/, "");
const VUS = Number(__ENV.VUS || 10);
const DURATION = __ENV.DURATION || "60s";
const THINK = Number(__ENV.THINK || 1);
const QUERY = __ENV.QUERY || "python";

// Names each request is reported under. Fixed rather than the URL, so that
// "?page=2" and "?q=python" do not each become a metric of their own.
export const NAMES = {
  page: "trang-danh-sach",
  pageSearch: "trang-tim-kiem",
  pageTwo: "trang-danh-sach-2",
  api: "api-danh-sach",
  apiSearch: "api-tim-kiem",
};

export const options = {
  // The test stack on a developer machine has a self-signed certificate.
  insecureSkipTLSVerify: __ENV.INSECURE_TLS === "1",
  scenarios: {
    duyet: { executor: "constant-vus", vus: VUS, duration: DURATION, exec: "visit" },
  },
  // Not pass/fail lines for a release -- declaring a threshold per name is how
  // k6 keeps a separate set of numbers for each, and the summary needs them.
  thresholds: {
    http_req_failed: ["rate<0.01"],
    [`http_req_duration{name:${NAMES.page}}`]: ["p(95)<2000"],
    [`http_req_duration{name:${NAMES.pageSearch}}`]: ["p(95)<2000"],
    [`http_req_duration{name:${NAMES.pageTwo}}`]: ["p(95)<2000"],
    [`http_req_duration{name:${NAMES.api}}`]: ["p(95)<500"],
    [`http_req_duration{name:${NAMES.apiSearch}}`]: ["p(95)<500"],
  },
  summaryTrendStats: ["count", "avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

function get(path, name) {
  const response = http.get(`${BASE_URL}${path}`, { tags: { name } });
  check(response, { [`${name}: 200`]: (r) => r.status === 200 });
  return response;
}

/** One person's visit. Exported so the class scenario can browse alongside. */
export function visit() {
  get("/khoa-hoc", NAMES.page);
  get("/api/v1/courses?page_size=12", NAMES.api);
  sleep(THINK);

  get(`/khoa-hoc?q=${QUERY}`, NAMES.pageSearch);
  get(`/api/v1/courses?q=${QUERY}&page_size=12`, NAMES.apiSearch);
  sleep(THINK);

  get("/khoa-hoc?page=2", NAMES.pageTwo);
  sleep(THINK);
}

export function handleSummary(data) {
  return summarize(data, `catalogue-${VUS}vu`);
}

/**
 * The numbers the report needs, as a file, plus a short table on stdout.
 * Written by hand rather than through k6's jslib, which is fetched from the
 * internet at run time.
 */
export function summarize(data, label) {
  const out = __ENV.OUT_DIR || "/out";
  const lines = [`\n${label}`];
  const row = (name, metric) => {
    if (!metric) return;
    const v = metric.values;
    lines.push(
      `  ${name.padEnd(34)} n=${String(v.count ?? "").padStart(6)}  ` +
        `med=${ms(v.med)}  p95=${ms(v["p(95)"])}  p99=${ms(v["p(99)"])}  max=${ms(v.max)}`,
    );
  };
  for (const key of Object.keys(data.metrics).sort()) {
    if (key.startsWith("http_req_duration{name:")) row(key.slice(23, -1), data.metrics[key]);
  }
  for (const key of Object.keys(data.metrics).sort()) {
    const metric = data.metrics[key];
    if (metric.type === "trend" && !key.startsWith("http_") && !key.startsWith("iteration")) {
      row(key, metric);
    }
  }
  const failed = data.metrics.http_req_failed?.values;
  const requests = data.metrics.http_reqs?.values;
  if (requests) {
    lines.push(
      `  requests ${requests.count} (${requests.rate.toFixed(1)}/s), ` +
        `failed ${((failed?.rate ?? 0) * 100).toFixed(2)}%`,
    );
  }
  const checks = data.metrics.checks?.values;
  if (checks) lines.push(`  checks ${checks.passes}/${checks.passes + checks.fails}`);
  return {
    stdout: lines.join("\n") + "\n",
    [`${out}/${label}.json`]: JSON.stringify(data, null, 2),
  };
}

function ms(value) {
  if (value === undefined) return "     -";
  return `${value.toFixed(0)}ms`.padStart(7);
}
