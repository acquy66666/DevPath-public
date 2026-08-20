# Frontend — Next.js

Giao diện web: trang public (SSR cho SEO), trải nghiệm học, dashboard giảng viên và admin.

Next.js 16 (App Router) · React 19 · TypeScript · Tailwind v4 · shadcn/ui (preset `radix-nova`, icon Lucide).

## Chạy local

```bash
npm install
```

```bash
npm run dev
```

Mở `http://localhost:3000`. Trang chủ hiển thị thẻ trạng thái backend — muốn thấy "Hoạt động" thì chạy backend trước (xem [backend/README.md](../backend/README.md)), nếu không nó hiện "Không kết nối được" mà trang vẫn sống.

Địa chỉ backend đọc từ `NEXT_PUBLIC_API_BASE_URL`, mặc định `http://127.0.0.1:8000` — copy [.env.example](.env.example) thành `.env.local` nếu cần đổi.

Kiểm tra trước khi commit:

```bash
npm run lint
```

```bash
npm run build
```

## Auth (Phase 2)

| Đường dẫn | Nội dung |
|---|---|
| `/dang-ky` | Form tạo tài khoản (họ tên, email, mật khẩu) |
| `/dang-nhap` | Form đăng nhập |

- `lib/api/auth.ts` — client typed khớp `backend/app/schemas/auth.py`.
- `lib/auth/auth-provider.tsx` — `AuthProvider` + hook `useAuth()`: `user`, `accessToken`, `status`, `signIn`, `signUp`, `signOut`.
- `lib/auth/validation.ts` — bản sao quy tắc validate của backend (mật khẩu ≥ 8 ký tự và ≤ 72 **byte**), chỉ để báo lỗi ngay cạnh ô nhập; backend vẫn là nơi quyết định.
- `lib/auth/error-messages.ts` — ánh xạ `code` của backend sang câu tiếng Việt. Không bao giờ switch theo `message`.

**Access token nằm trong bộ nhớ, không ở `localStorage` cũng không ở cookie JS đọc được.** Refresh token là cookie `HttpOnly` của backend, nên F5 xong `AuthProvider` gọi `/auth/refresh` để dựng lại phiên — đó là lúc header hiện ô xám chờ (`status === "loading"`). Đánh đổi: `middleware.ts` của Next không đọc được cookie đó nên guard route phải làm ở client; chưa có route nào cần guard cho tới khi có trang học.

**Cạm bẫy đã gặp: refresh gọi hai lần là mất phiên.** Backend xoay vòng refresh token và coi token đã thu hồi quay lại là bị đánh cắp (thu hồi sạch phiên). React StrictMode chạy effect hai lượt trong dev ⇒ hai request refresh song song ⇒ tự đăng xuất chính mình. `lib/api/auth.ts` vì thế gom mọi lời gọi refresh đang bay vào **một** promise duy nhất. Hệ quả còn lại: mở hai tab cùng lúc sau khi để lâu vẫn có thể chạm vào tình huống này — nếu thành phiền thì thêm khoảng ân hạn (leeway) phía backend.

## Cấu trúc

```
app/
├── (marketing)/     Trang public: home, danh sách + chi tiết khóa học (SSR, SEO)
├── (learn)/         Player, quiz, code editor (client-heavy) — Phase 2+
└── (dashboard)/     Instructor + admin — Phase 2+
components/ui/       shadcn/ui (generated, hạn chế sửa tay)
components/layout/   site-header, site-footer
components/<domain>/ course-card, video-player, code-editor... — Phase 2+
lib/api/             API client typed, 1 file mỗi domain
```

## Nguyên tắc

- **Server Component mặc định**; chỉ `"use client"` khi thật sự cần state/effect/event.
- Mọi call API đi qua [lib/api/client.ts](lib/api/client.ts) — không rải `fetch` trong component. Không dùng `app/api/` của Next.js, backend là FastAPI.
- Tailwind + shadcn/ui, không thêm UI library khác.
- Mỗi route segment có `loading.tsx` và `error.tsx`; danh sách rỗng phải có empty state tử tế.

Chi tiết: skill `nextjs-feature` trong `.claude/skills/`.

## Hai cái bẫy của Next.js 16 đã gặp

**Component gọi API phải `await connection()`.** Không có nó, trang bị prerender lúc build và kết quả API bị đóng băng vào HTML tĩnh — trạng thái backend sẽ luôn hiện như lúc chạy `npm run build`. Kết hợp với `<Suspense>` để phần tĩnh của trang vẫn được prerender bình thường.

**Không dựng JSX bên trong `try/catch`.** ESLint (`react-hooks/error-boundaries`) chặn, và đúng: lỗi render của component con sẽ bị `catch` nuốt nhầm. Await trong `try`, gán kết quả ra biến, rồi mới render bên ngoài.

`AGENTS.md` và `CLAUDE.md` trong thư mục này do `next dev` tự sinh và tự thêm lại — chúng chỉ tới bộ doc trong `node_modules/next/dist/docs/`, là nguồn chính xác nhất cho phiên bản đang dùng.
