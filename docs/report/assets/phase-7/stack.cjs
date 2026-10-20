/**
 * Đường tới stack cho các script chụp ảnh và đo của Phase 7 (`measure.cjs`,
 * `phase-6/ui/capture.cjs`).
 *
 * `RESOLVE_TO=127.0.0.1` cho tên miền của stack trỏ thẳng vào nginx trên máy
 * này thay vì đi vòng qua Cloudflare — cả trong Chrome (`--host-resolver-rules`)
 * lẫn ở các lệnh gọi API từ Node. Vẫn là bản build production, vẫn nginx,
 * TLS, HTTP/2, vẫn tên miền thật trên thanh địa chỉ (cookie, CSP, canonical
 * như người dùng thấy). Lý do:
 *   - mật khẩu tài khoản seed và tài khoản dùng một lần không rời máy này;
 *   - số đo không lẫn độ trễ Internet/tunnel, thứ đổi theo giờ trong ngày, nên
 *     "trước" và "sau" so được với nhau;
 *   - không có beacon RUM mà edge Cloudflare tự chèn vào HTML — không phải JS
 *     của DevPath.
 * nginx trên máy dev dùng chứng chỉ tự ký cho tên miền (Cloudflare mới cầm
 * chứng chỉ thật), nên chỉ ở chế độ này mới bỏ qua lỗi chứng chỉ.
 *
 * Không đặt `RESOLVE_TO` thì mọi thứ đi đường thường (stack dev ở localhost,
 * hoặc VPS qua DNS thật).
 */
const http = require("node:http");
const https = require("node:https");

const RESOLVE_TO = process.env.RESOLVE_TO || "";

function stack(base) {
  const host = new URL(base).hostname;
  const mapped = Boolean(RESOLVE_TO) && host !== RESOLVE_TO;

  /** Tham số cho `chromium.launch*`: Chrome hỏi đúng chỗ Node hỏi. */
  const chromeArgs = mapped
    ? [`--host-resolver-rules=MAP ${host} ${RESOLVE_TO}`, "--ignore-certificate-errors"]
    : [];

  function lookup(name, options, callback) {
    if (options.all) callback(null, [{ address: RESOLVE_TO, family: 4 }]);
    else callback(null, RESOLVE_TO, 4);
  }

  /** Một request HTTP từ Node. Trả về status, header, thân (Buffer). */
  function request(method, url, { headers = {}, body } = {}) {
    const target = new URL(url);
    const local = mapped && target.hostname === host;
    const transport = target.protocol === "https:" ? https : http;
    return new Promise((resolve, reject) => {
      const req = transport.request(
        target,
        {
          method,
          headers,
          timeout: 180_000,
          ...(local ? { lookup, rejectUnauthorized: false } : {}),
        },
        (res) => {
          const chunks = [];
          res.on("data", (chunk) => chunks.push(chunk));
          res.on("end", () =>
            resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }),
          );
          res.on("error", reject);
        },
      );
      req.on("timeout", () => req.destroy(new Error(`${method} ${url}: hết giờ`)));
      req.on("error", reject);
      if (body) req.write(body);
      req.end();
    });
  }

  return { host, mapped, chromeArgs, request };
}

/**
 * Gọi API kiểu JSON. `session` là { token, cookie } của một lần đăng nhập qua
 * API — cookie refresh được giữ để `logout` thu hồi đúng phiên đó.
 */
function apiClient(base, api = base) {
  const { request } = stack(base);
  const root = `${api.replace(/\/$/, "")}/api/v1`;

  async function call(method, path, { token, data, cookie, raw = false } = {}) {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    if (cookie) headers.Cookie = cookie;
    let body;
    if (data !== undefined) {
      body = Buffer.from(JSON.stringify(data));
      headers["Content-Type"] = "application/json";
      headers["Content-Length"] = String(body.length);
    }
    const response = await request(method, `${root}${path}`, { headers, body });
    const text = response.body.toString("utf8");
    if (response.status >= 400) throw new Error(`${method} ${path}: ${response.status} ${text.slice(0, 300)}`);
    if (raw) return { ...response, text };
    return text ? JSON.parse(text) : {};
  }

  function refreshCookie(response) {
    const set = [response.headers["set-cookie"] ?? []].flat();
    return set.map((line) => line.split(";")[0]).filter((pair) => !pair.endsWith("=")).join("; ");
  }

  async function login(account) {
    const response = await call("POST", "/auth/login", { data: account, raw: true });
    return { token: JSON.parse(response.text).access_token, cookie: refreshCookie(response) };
  }

  async function register(account) {
    const response = await call("POST", "/auth/register", { data: account, raw: true });
    return { token: JSON.parse(response.text).access_token, cookie: refreshCookie(response) };
  }

  async function logout(session) {
    if (!session?.cookie) return;
    await call("POST", "/auth/logout", { cookie: session.cookie }).catch(() => {});
  }

  return { call, login, register, logout };
}

/**
 * Tên và email của người dùng thật trên stack — mọi tài khoản có email không
 * kết thúc bằng `.example` (seed, người mua mẫu, tài khoản dùng một lần đều là
 * `.example`). Trên stack demo đó là tài khoản Google của user, có trong danh
 * sách người dùng, cấp giảng viên… Không đọc được CSDL thì trả về rỗng.
 */
function realUsers(project) {
  const { execFileSync } = require("node:child_process");
  try {
    const id = execFileSync(
      "docker",
      ["ps", "-q", "--filter", `label=com.docker.compose.project=${project}`, "--filter", "label=com.docker.compose.service=postgres"],
      { encoding: "utf8" },
    ).trim().split("\n")[0];
    if (!id) return [];
    const out = execFileSync(
      "docker",
      ["exec", id, "sh", "-c", `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F '|' -c "select full_name, email from users where email not like '%.example'"`],
      { encoding: "utf8" },
    ).trim();
    return out ? [...new Set(out.split("\n").flatMap((line) => line.split("|")).filter(Boolean))] : [];
  } catch {
    return [];
  }
}

/**
 * Làm mờ (CSS blur, ngay trước khi chụp) mọi phần tử có chữ chứa tên/email của
 * người dùng thật, và mọi ảnh đại diện Google. Trả về số chỗ đã che.
 */
async function blurPrivate(page, needles) {
  return page.evaluate((needles) => {
    const hits = new Set();
    if (needles.length) {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (needles.some((needle) => node.nodeValue.includes(needle))) hits.add(node.parentElement);
      }
      for (const field of document.querySelectorAll("input, textarea")) {
        if (needles.some((needle) => field.value.includes(needle))) hits.add(field);
      }
    }
    for (const img of document.querySelectorAll('img[src*="googleusercontent"]')) hits.add(img);
    for (const element of hits) element.style.filter = "blur(6px)";
    return hits.size;
  }, needles);
}

module.exports = { stack, apiClient, realUsers, blurPrivate, RESOLVE_TO };
