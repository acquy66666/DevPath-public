# ExportButton

"Xuất Excel" trên mọi trang thống kê: tải tệp `export.xlsx` song sinh với trang, dựng ở máy chủ từ đúng lời gọi service mà trang đọc, nên tệp không bao giờ lệch với màn hình.

**Code:** `frontend/components/ui/export-button.tsx`. Bên dùng truyền `path` (đường dẫn `export.xlsx`), `filename` dự phòng, và tùy chọn `label`, `size`.

## Luật

- Là một `Button` `outline` cỡ `sm`, icon bảng tính 16px. Hành động trung tính, nên không bao giờ là `primary`.
- Đang tải: `disabled`, icon thành vòng quay, nhãn "Đang xuất…". Chiều rộng gần như giữ nguyên.
- Lỗi: một dòng 12px `destructive-text` ngay dưới nút, căn phải theo nút, `role="alert"`, nói chuyện gì xảy ra và cách thử lại. Lỗi không bị nuốt.
- Tên tệp do máy chủ đặt (`Content-Disposition`); `filename` chỉ dùng khi máy chủ không đặt.
