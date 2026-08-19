# ĐỀ CƯƠNG KHÓA LUẬN TỐT NGHIỆP

## Tên đề tài (đề xuất)
**"Xây dựng nền tảng học trực tuyến tích hợp AI với hệ thống chấm mã nguồn tự động và gợi ý khóa học cá nhân hóa"**

*(Tên tiếng Anh: Building an AI-Integrated E-Learning Platform with Automated Code Grading and Personalized Course Recommendation)*

---

## 1. Lý do chọn đề tài
- Nhu cầu học trực tuyến tại Việt Nam tăng mạnh, nhưng các nền tảng nội địa còn thiếu tính năng tương tác sâu (chấm bài tự động, gợi ý cá nhân hóa, trợ lý AI).
- Đề tài mang tính tổng hợp cao về CNTT: full-stack web, hệ thống phân tán, DevOps (Docker sandbox), AI/ML (recommender + chatbot RAG) — thể hiện được nhiều kỹ năng trong một sản phẩm.
- Sản phẩm có khả năng vận hành thực tế với chi phí thấp, có thể phát triển tiếp sau khóa luận.

## 2. Mục tiêu
- Xây dựng nền tảng e-learning hoàn chỉnh kiểu Udemy: đăng khóa học, học video, thanh toán, đánh giá, chứng chỉ.
- Điểm nhấn kỹ thuật 1: **hệ thống chấm mã nguồn tự động** chạy trong Docker sandbox (an toàn, cô lập, đa ngôn ngữ).
- Điểm nhấn kỹ thuật 2: **hệ gợi ý lai (hybrid recommender)** kết hợp collaborative filtering + content-based.
- Điểm nhấn kỹ thuật 3: **chatbot AI trợ giảng** dùng RAG trên nội dung khóa học.

## 3. Điểm mạnh của đề tài
| Điểm mạnh | Giải thích |
|---|---|
| Nhiều tính năng| 3 nhóm người dùng (học viên, giảng viên, admin), 20+ tính năng liệt kê ở mục 5 |
| Có chiều sâu kỹ thuật, không chỉ CRUD | Docker sandbox grading và recommender là bài toán hệ thống thực sự, ít khóa luận làm |
| Chi phí vận hành thấp | Self-host/VPS giá rẻ, model AI qua API free-tier (Gemini), video lưu qua object storage rẻ |
| Dữ liệu demo dễ tạo | Có thể seed khóa học lập trình thật để demo end-to-end |
| Tiềm năng sản phẩm dài hạn | Có thể thương mại hóa cho thị trường học lập trình Việt Nam |

## 4. Kiến trúc & công nghệ đề xuất
- **Frontend:** Next.js (SSR, SEO tốt cho trang khóa học)
- **Backend:** FastAPI (REST API) — tận dụng kinh nghiệm sẵn có
- **CSDL:** PostgreSQL + Redis (cache, session, leaderboard)
- **Hàng đợi:** Celery/RQ — xếp hàng job chấm bài
- **Chấm bài:** Docker sandbox (giới hạn CPU/RAM/time, network tắt), test case ẩn
- **AI:** Gemini API (chatbot RAG + sinh quiz), embedding cho gợi ý content-based
- **Video:** HLS streaming, lưu trên object storage (Cloudflare R2 — egress miễn phí)
- **Thanh toán:** VNPay/MoMo sandbox
- **Triển khai:** Docker Compose trên VPS

## 5. Các tính năng nổi bật

### 5.1. Nhóm học viên
1. Đăng ký/đăng nhập (OAuth Google), phân quyền JWT
2. Duyệt & tìm kiếm khóa học (full-text search, lọc theo danh mục, giá, rating)
3. Xem video HLS, ghi nhớ tiến độ xem, tốc độ phát, phụ đề
4. **Nộp bài code — chấm tự động trong Docker sandbox, trả kết quả test case realtime** ⭐
5. Quiz trắc nghiệm có tính giờ, tự động chấm
6. **Chatbot AI trợ giảng (RAG trên transcript + tài liệu khóa học)** ⭐
7. **Gợi ý khóa học cá nhân hóa (hybrid recommender)** ⭐
8. Ghi chú theo timestamp video, đánh dấu bài học
9. Hỏi đáp (Q&A) theo bài học, upvote
10. Chứng chỉ hoàn thành (PDF tự sinh, mã QR xác thực)
11. Gamification: streak học tập, điểm XP, leaderboard
12. Giỏ hàng, thanh toán, mã giảm giá, wishlist

### 5.2. Nhóm giảng viên
13. Tạo/quản lý khóa học (curriculum kéo-thả, upload video)
14. Tạo bài tập code: đề bài, test case, giới hạn tài nguyên
15. **Sinh quiz tự động bằng AI từ nội dung bài giảng** ⭐
16. Dashboard doanh thu, thống kê học viên, tỉ lệ hoàn thành
17. Trả lời Q&A, thông báo đến học viên

### 5.3. Nhóm quản trị
18. Duyệt khóa học, quản lý người dùng, xử lý báo cáo
19. Dashboard toàn hệ thống (doanh thu, DAU, khóa học hot)
20. Quản lý danh mục, banner, mã giảm giá toàn sàn

## 6. Hướng phát triển 
- **Live class:** lớp học trực tiếp qua WebRTC, chat realtime
- **Học nhóm & peer review:** chấm chéo bài tập tự luận
- **Mobile app** (React Native) dùng chung API
- **Proctoring nhẹ cho thi:** phát hiện chuyển tab, giới hạn thời gian
- **Recommender nâng cao:** học sâu (sequence-based, ví dụ SASRec) khi có dữ liệu người dùng thật
- **Đa ngôn ngữ chấm bài:** mở rộng sandbox sang Java, C++, Go
- **Marketplace:** chia sẻ doanh thu giảng viên, affiliate

## 7. Phạm vi & kế hoạch dự kiến (12–14 tuần)
| Giai đoạn | Nội dung | Thời gian |
|---|---|---|
| 1 | Khảo sát, thiết kế CSDL, wireframe | Tuần 1–2 |
| 2 | Auth, quản lý khóa học, video streaming | Tuần 3–5 |
| 3 | Docker sandbox grading + hàng đợi | Tuần 6–8 |
| 4 | Recommender + chatbot RAG + sinh quiz | Tuần 9–10 |
| 5 | Thanh toán, gamification, admin | Tuần 11–12 |
| 6 | Kiểm thử, triển khai, viết báo cáo | Tuần 13–14 |

## 8. Kết quả kỳ vọng
- Sản phẩm web chạy được trên môi trường thật (VPS), demo end-to-end.
- Báo cáo khóa luận trình bày kiến trúc hệ thống, thiết kế sandbox an toàn, đánh giá recommender (precision@k, recall@k) và chất lượng chatbot.
