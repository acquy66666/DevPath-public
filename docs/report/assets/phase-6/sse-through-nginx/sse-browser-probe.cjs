// Drill only: SSE timing in a real Chrome via the prodtest nginx (see run notes).
const fs = require("node:fs");
const { chromium } = require("@playwright/test");
const [ctxFile, outFile] = process.argv.slice(2);
const { token, sessions } = JSON.parse(fs.readFileSync(ctxFile, "utf8"));
const QUESTIONS = [
  "Giải thích thật chi tiết cách đọc một thông báo lỗi Traceback trong Python, từng phần một.",
  "Ép kiểu trong Python có những cái bẫy nào? Liệt kê và giải thích từng cái kèm ví dụ.",
  "Biến local và global khác nhau thế nào, và vì sao nên tránh dùng global? Giải thích kỹ.",
];
(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto("https://localhost/");
  fs.writeFileSync(outFile, "");
  for (let q = 0; q < QUESTIONS.length; q += 1) {
    const result = await page.evaluate(async ({ token, sid, question }) => {
      const started = performance.now();
      const response = await fetch(`/api/v1/chat-sessions/${sid}/messages`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ content: question }),
      });
      const headersAt = Math.round(performance.now() - started);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ""; let reads = 0; const events = [];
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        reads += 1;
        const at = Math.round(performance.now() - started);
        buffer += decoder.decode(value, { stream: true });
        let cut;
        while ((cut = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
          const name = (frame.match(/^event: (.*)$/m) || [])[1] || "?";
          const data = (frame.match(/^data: (.*)$/m) || [])[1] || "{}";
          events.push([at, name, name === "delta" ? (JSON.parse(data).text || "").length : 0]);
        }
      }
      const entry = performance.getEntriesByType("resource").filter((e) => e.name.includes(sid)).pop();
      return { status: response.status, headers_ms: headersAt, socket_reads: reads,
        protocol: entry ? entry.nextHopProtocol : null,
        headers: { "Content-Type": response.headers.get("content-type"),
          "Transfer-Encoding": response.headers.get("transfer-encoding"),
          "Content-Encoding": response.headers.get("content-encoding"),
          "X-Accel-Buffering": response.headers.get("x-accel-buffering") },
        events };
    }, { token, sid: sessions[q], question: QUESTIONS[q] });
    fs.appendFileSync(outFile, JSON.stringify({ path: `chrome-${result.protocol}`, q, r: result }) + "\n");
    await page.waitForTimeout(4000);
  }
  await browser.close();
})();
