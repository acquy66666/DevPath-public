# Lên giảng viên qua admin duyệt (02/11/2026)

Task ngoài kế hoạch, user yêu cầu. Nhánh `feature/instructor-application`. **Ngoại lệ luật "backend đứng yên" của Phase 7** (cần bảng + endpoint mới).

## Trước và sau

| | Trước | Sau |
|---|---|---|
| Học viên lên giảng viên | `POST /users/me/instructor` — một cú bấm, ai cũng tự lên | `POST /users/me/instructor-application` (lời giới thiệu tùy chọn) → **chờ admin** |
| Ai đổi `users.role` | Chính người đó | Chỉ admin, lúc duyệt (`POST /admin/instructor-applications/{id}/approve`) |
| Từ chối | — | Bắt buộc lý do; học viên đọc nguyên văn, sửa rồi gửi lại |
| Báo kết quả | — | Thông báo `instructor_application_approved` / `_rejected`, cùng transaction với quyết định |

Route cũ đã **bỏ hẳn**: còn nó thì cửa duyệt vô nghĩa. Giảng viên tự lên trước đây giữ nguyên vai.

## Thiết kế

- Bảng `instructor_applications` (migration `7c885a800a6a`, chi tiết ở `docs/database-design.md` §1): một yêu cầu đang chờ mỗi người (partial unique), CHECK `decided_at` ⇔ đã quyết, CHECK lý do ⇔ bị từ chối. Dòng cũ giữ làm lịch sử ("từng bị từ chối N lần" trên màn admin).
- Service `app/services/instructor_applications.py`: khóa dòng yêu cầu + dòng `users` `FOR UPDATE`; quyết định hai lần → 409 `INSTRUCTOR_APPLICATION_DECIDED`; vai đã đổi tay (vd. thành admin) thì không ghi đè → 409 `ROLE_CHANGE_NOT_ALLOWED`.
- `GET /admin/summary` thêm `pending_instructor_applications` → huy hiệu mục "Duyệt giảng viên" (nhóm Kiểm duyệt) + thẻ "Yêu cầu làm giảng viên" ở "Cần xử lý".
- Frontend: thẻ ở `/tro-thanh-giang-vien` có 4 trạng thái (gửi / đang chờ / bị từ chối kèm lý do + gửi lại / đã duyệt). Cổng `/giang-day` đọc lại phiên một lần khi gặp học viên: bấm thông báo "đã được duyệt" là vào thẳng, không cần tải lại trang.
- E2E `e2e/support/stack.ts` dựng giảng viên bằng đúng đường mới (gửi yêu cầu → admin seed duyệt).

## Kiểm

- Migration: `alembic upgrade head` → `downgrade -1` → `upgrade head` → `alembic check` ("No new upgrade operations detected").
- pytest: `test_instructor_applications.py` 19 ca; ma trận phân quyền có luật cho 2 route học viên (route `/admin/*` tự xếp loại) và một yêu cầu của learner trong `LEARNER_PRIVATE`. Toàn bộ: xem PR.
- `npm test` 156/156, `npm run lint` + `tsc --noEmit` sạch, `next build` (không mạng) xanh có `/quan-tri/duyet-giang-vien`.
- E2E `npm run test:e2e`: **10 passed** (axe 4 vai × 1440/375 gồm trang mới, luồng vàng, luồng bàn phím).
- Chạy thật trên stack dev — [`instructor-application/flow.cjs`](instructor-application/flow.cjs), 12/12 kiểm:
  học viên gửi → thấy "đang chờ" → `/giang-day` vẫn từ chối (không vòng refresh) → admin thấy huy hiệu số chờ → duyệt A, từ chối B kèm lý do → A bấm thông báo trong cùng tab, vào `/giang-day` không tải lại → B thấy lý do + nút "Gửi lại yêu cầu" → 0 tràn ngang ở 360 px (trang học viên + hàng đợi admin).
- **Lỗi tìm ra khi chạy thật:** ô nhập mới làm trang `/tro-thanh-giang-vien` tràn 22 px ở 360 px (lưới không đặt cột ở cỡ điện thoại) → `grid-cols-[minmax(0,1fr)]`.

## Chưa làm

- `npm run test:visual` chưa chạy (cần stack sạch `devpath-visual`): menu admin thêm một mục và "Cần xử lý" thành 4 thẻ, nên baseline các màn admin sẽ đổi có chủ đích — cần `--update-snapshots` trên stack sạch rồi mở từng ảnh.
- Các script chụp/đo cũ trong `docs/report/assets/` còn gọi `POST /users/me/instructor` (phase-6 `ui/capture.cjs`, `ffmpeg-hardening/upload_drill.py`, `upload-ticket-rate-limit/ticket_drill.py`; phase-7 `admin/stage.cjs`, `article-editor/run.cjs`, `instructor/stage.cjs`, `site-states/capture.cjs`): chạy lại thì phải đổi sang gửi yêu cầu + admin duyệt như `e2e/support/stack.ts`.

## Ảnh

`instructor-application/`: form gửi (1440), đang chờ, tổng quan admin với thẻ mới, hàng đợi, đang từ chối, khu giảng dạy sau khi duyệt, học viên bị từ chối (360), hàng đợi "Tất cả" (360).
