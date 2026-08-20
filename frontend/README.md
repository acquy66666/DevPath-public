# Frontend — Next.js

Giao diện web: trang public (SSR cho SEO), trải nghiệm học, dashboard giảng viên và admin.

## Thư mục này đang trống có chủ đích

Next.js sẽ được scaffold bằng `create-next-app` ở task kế tiếp của [Phase 1](../docs/plan/phase-1-foundation.md). `create-next-app` từ chối chạy trong thư mục đã có `app/` hoặc `package.json`, nên khung thư mục **không** được tạo sẵn ở đây — chỉ có file README này (nằm trong danh sách file `create-next-app` chấp nhận).

## Cấu trúc sẽ dựng

```
app/
├── (marketing)/     Trang public: home, danh sách + chi tiết khóa học (SSR, SEO)
├── (learn)/         Player, quiz, code editor (client-heavy)
└── (dashboard)/     Instructor + admin
components/ui/       shadcn/ui (generated, hạn chế sửa tay)
components/<domain>/ course-card, video-player, code-editor...
lib/api/             API client typed, 1 file mỗi domain
```

## Nguyên tắc

- **Server Component mặc định**; chỉ `"use client"` khi thật sự cần state/effect/event.
- Mọi call API đi qua `lib/api/client.ts` — không rải `fetch` trong component. Không dùng `app/api/` của Next.js, backend là FastAPI.
- Tailwind + shadcn/ui, không thêm UI library khác.
- Mỗi route segment có `loading.tsx` và `error.tsx`; danh sách rỗng phải có empty state tử tế.

Chi tiết: skill `nextjs-feature` trong `.claude/skills/`.
