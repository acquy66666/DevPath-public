// The whole flow on the dev stack, through the real UI: a throwaway student
// picks a new avatar on /ho-so, the API signs a ticket for the file's size,
// Chrome PUTs it straight to the bucket (minio.localhost:9000, HTTP/1.1,
// CORS), and the profile saves it.
//
//   NODE_PATH=frontend/node_modules node docs/report/assets/phase-6/signed-upload-length/avatar-ui.cjs
//   docker compose -f infra/docker-compose.yml exec backend python -m scripts.purge_e2e
//
// The account is @e2e.devpath.example, so purge_e2e removes it.
const zlib = require("zlib");
const { chromium } = require("playwright");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const API = process.env.API_URL || "http://localhost:8000";

/** A real PNG, `side` px square, noisy enough that it does not compress to nothing. */
function png(side) {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([length, body, sum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(side, 0);
  header.writeUInt32BE(side, 4);
  header[8] = 8; // bit depth
  header[9] = 2; // RGB
  const rows = [];
  let seed = 7;
  for (let y = 0; y < side; y++) {
    const row = Buffer.alloc(1 + side * 3);
    for (let i = 1; i < row.length; i++) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      row[i] = seed >> 16;
    }
    rows.push(row);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

(async () => {
  const account = {
    email: `upload-${Date.now()}@e2e.devpath.example`,
    password: "devpath-upload-check",
    full_name: "Kiểm tải ảnh",
  };
  const browser = await chromium.launch({ channel: "chrome" });
  const context = await browser.newContext();
  const created = await context.request.post(`${API}/api/v1/auth/register`, { data: account });
  if (!created.ok()) throw new Error(`register: ${created.status()}`);

  const page = await context.newPage();
  await page.goto(`${BASE}/dang-nhap`, { waitUntil: "domcontentloaded" });
  // As ui/capture.cjs: a click before React owns the form submits it as GET.
  await page.waitForFunction(
    () => {
      const forms = document.querySelectorAll("form");
      return forms.length === 1 && Object.keys(forms[0]).some((k) => k.startsWith("__reactProps"));
    },
    null,
    { timeout: 60_000 },
  );
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mật khẩu").fill(account.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/dang-nhap"), { timeout: 45_000 });

  await page.goto(`${BASE}/ho-so`, { waitUntil: "domcontentloaded" });
  const picture = png(180);
  const ticketAnswer = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/users/me/avatar") && r.request().method() === "POST",
    { timeout: 60_000 },
  );
  const putAnswer = page.waitForResponse((r) => r.request().method() === "PUT", { timeout: 60_000 });
  const doneAnswer = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/users/me/avatar/complete") && r.request().method() === "POST",
    { timeout: 60_000 },
  );
  await page
    .locator('input[type="file"]')
    .setInputFiles({ name: "chan-dung.png", mimeType: "image/png", buffer: picture });

  const ticketResponse = await ticketAnswer;
  const asked = JSON.parse(ticketResponse.request().postData());
  const ticket = await ticketResponse.json();
  const signedHeaders = new URL(ticket.upload_url).searchParams.get("X-Amz-SignedHeaders");
  const put = await putAnswer;
  const putHeaders = await put.request().allHeaders();
  const done = await doneAnswer;

  // What the bucket now serves at the address the profile saved.
  const saved = await done.json();
  // From the page, as the <img> in the header reads it: Node on Windows does
  // not resolve *.localhost, Chrome does.
  const served = await page.evaluate(async (url) => {
    const response = await fetch(url);
    return { ok: response.ok, status: response.status, bytes: (await response.arrayBuffer()).byteLength };
  }, saved.avatar_url);
  const servedBytes = served.bytes;

  const checks = [
    ["file picked", true, `${picture.length} B PNG`],
    ["ticket asked for the file's size", asked.size_bytes === picture.length, `size_bytes=${asked.size_bytes}`],
    ["ticket signs the length", signedHeaders === "content-length;content-type;host", signedHeaders],
    ["Chrome PUT straight to the bucket", put.status() === 200, `HTTP ${put.status()} ${new URL(put.url()).host}, content-length ${putHeaders["content-length"] ?? "(set by the network stack)"}`],
    ["profile saved the picture", done.ok() && Boolean(saved.avatar_url), `HTTP ${done.status()}`],
    ["bucket serves exactly that file", served.ok && servedBytes === picture.length, `HTTP ${served.status}, ${servedBytes} B`],
  ];
  let failed = 0;
  for (const [label, ok, detail] of checks) {
    failed += ok ? 0 : 1;
    console.log(`${ok ? "PASS" : "FAIL"}  ${label.padEnd(36)} ${detail}`);
  }

  await context.request.post(`${API}/api/v1/auth/logout`).catch(() => {});
  await browser.close();
  console.log(`${checks.length - failed}/${checks.length}  (account ${account.email} -- run purge_e2e)`);
  process.exit(failed ? 1 : 0);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
