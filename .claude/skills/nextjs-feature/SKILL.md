---
name: nextjs-feature
description: Use when building pages, components, or data fetching in the Next.js frontend — App Router conventions, server/client component split, API client pattern, styling with Tailwind + shadcn/ui.
---

# Xây tính năng frontend Next.js

## Cấu trúc

```
frontend/
├── app/                      # App Router
│   ├── (marketing)/          # Trang public: home, danh sách khóa học, chi tiết khóa học (SSR cho SEO)
│   ├── (learn)/              # Trải nghiệm học: player, quiz, code editor (client-heavy)
│   ├── (dashboard)/          # Instructor + admin dashboards
│   └── api/                  # KHÔNG dùng — mọi API đi qua FastAPI backend
├── components/ui/            # shadcn/ui components (generated, hạn chế sửa tay)
├── components/<domain>/      # Component nghiệp vụ: course-card, video-player, code-editor...
└── lib/api/                  # API client: 1 file per domain, typed bằng interface khớp Pydantic schema
```

## Quy tắc

1. **Server Component mặc định.** Chỉ thêm `"use client"` khi thật sự cần state/effect/event. Trang course listing + course detail phải SSR (yêu cầu SEO trong đề cương).
2. **Data fetching:** Server Component fetch trực tiếp (có cache tags); Client Component dùng TanStack Query. Không fetch trong useEffect.
3. **API client:** mọi call qua `lib/api/client.ts` (base fetch có attach JWT, refresh token, parse lỗi `{detail: {code}}`). Không gọi `fetch` rải rác trong component.
4. **Auth:** JWT lưu httpOnly cookie; middleware.ts guard các route group `(learn)` và `(dashboard)`. Role check hiển thị UI, nhưng authorization thật nằm ở backend.
5. **Styling:** Tailwind + shadcn/ui. Không thêm UI library khác, không viết CSS file riêng trừ globals.
6. **Loading/error:** mỗi route segment có `loading.tsx` (skeleton) và `error.tsx`. List rỗng phải có empty state tử tế — sản phẩm demo hội đồng, ấn tượng thị giác quan trọng.
7. **Component nặng** (video player HLS, Monaco code editor) → dynamic import `ssr: false`, có skeleton.
8. **Tiếng Việt trước:** UI text tiếng Việt, hardcode được ở giai đoạn này (i18n là hướng phát triển, không làm sớm).

## Trang trọng điểm cần đầu tư UX

Trang chi tiết khóa học, video player (ghi nhớ tiến độ, tốc độ phát, note theo timestamp), trang nộp code (editor + kết quả test case realtime qua polling/WebSocket), dashboard giảng viên.
