# Khảo sát nền tảng tham chiếu

> Tài liệu bằng chứng cho **Chương 1 — Mở đầu** (mục "Khảo sát hiện trạng") và **Chương 3 — Phân tích & thiết kế** (mục "Xác định yêu cầu chức năng").
> Ngày khảo sát: **19/08/2026**. Nguồn: tài liệu hỗ trợ chính thức của nhà cung cấp và bài viết báo chí công nghệ (liệt kê ở mục 6).

## 1. Mục tiêu và phương pháp khảo sát

Khảo sát nhằm ba mục đích: (1) xác định tập tính năng nền tảng (baseline) mà một hệ thống học trực tuyến hiện đại bắt buộc phải có; (2) nhận diện khoảng trống (gap) mà các nền tảng hiện hữu chưa đáp ứng cho người học lập trình tại Việt Nam; (3) làm căn cứ định vị ba điểm nhấn kỹ thuật của đề tài.

Ba nền tảng được chọn theo nguyên tắc **mỗi nền tảng đại diện cho một mô hình khác nhau**, tránh khảo sát ba hệ thống trùng loại:

| Nền tảng | Mô hình đại diện | Lý do chọn |
|---|---|---|
| **Udemy** | Marketplace khóa học mở (C2C) | Mô hình mục tiêu của đề tài: giảng viên tự đăng khóa học, người học mua lẻ |
| **Coursera** | MOOC hợp tác đại học/doanh nghiệp (B2B2C) | Đại diện chuẩn mực học thuật: lộ trình, chứng chỉ, đánh giá có kiểm định |
| **CodeLearn.io** | Nền tảng luyện lập trình nội địa (FPT Software) | Đối thủ trực tiếp tại thị trường Việt Nam, mạnh về chấm mã nguồn tự động |

**Phương pháp:** nghiên cứu tài liệu (documentation research) trên tài liệu hỗ trợ chính thức, blog sản phẩm và báo chí công nghệ; đối chiếu chéo giữa các nguồn khi số liệu không thống nhất. Hạn chế của phương pháp được nêu ở mục 5.

## 2. Tổng quan ba nền tảng

| Tiêu chí | Udemy | Coursera | CodeLearn.io |
|---|---|---|---|
| Chủ sở hữu | Udemy, Inc. (Hoa Kỳ) | Coursera, Inc. (Hoa Kỳ) | FPT Software (Việt Nam) |
| Nguồn gốc | Marketplace thương mại | Liên kết đại học (Stanford) | Phát triển từ nền tảng thi lập trình CodeWar Fsoft & FJP (2018) |
| Nguồn nội dung | Giảng viên cá nhân tự đăng | Đại học, tổ chức, doanh nghiệp đối tác | Đội ngũ nội bộ biên soạn |
| Mô hình doanh thu | Mua lẻ khóa học + thuê bao doanh nghiệp (Udemy Business) | Thuê bao (Coursera Plus) + học phí chứng chỉ/bằng cấp | Chủ yếu miễn phí, hướng cộng đồng và tuyển dụng |
| Trọng tâm nội dung | Đa lĩnh vực (CNTT, kinh doanh, thiết kế...) | Học thuật, cấp chứng chỉ/bằng | Chuyên sâu lập trình và thuật toán |
| Ngôn ngữ giao diện | Đa ngôn ngữ (có tiếng Việt) | Đa ngôn ngữ (có tiếng Việt) | Tiếng Việt (bản địa) |
| Quy mô nội dung liên quan | Thư viện bài tập code hỗ trợ **22 ngôn ngữ/môi trường** | Hàng nghìn khóa học, lab lập trình chấm tự động | **19 khóa ngôn ngữ lập trình**, hơn **1.550–2.000 bài tập** thực hành |

*Ghi chú số liệu:* số bài tập của CodeLearn được các nguồn ghi nhận khác nhau theo thời điểm công bố (hơn 1.550 ở nguồn [7], hơn 2.000 ở nguồn [4]); tài liệu này ghi nhận cả hai khoảng giá trị thay vì chọn một con số duy nhất.

## 3. Bảng so sánh tính năng chi tiết

**Chú thích ký hiệu:** ✔ có đầy đủ · ◐ có nhưng giới hạn (theo gói cước, theo ngôn ngữ, hoặc phạm vi hẹp) · ✘ không có/không công bố · ★ điểm nhấn kỹ thuật của đề tài.

Cột **"Hệ thống đề xuất"** ánh xạ tới danh sách 20 tính năng trong đề cương (mục 5); số trong ngoặc là số thứ tự tính năng tương ứng.

### 3.1. Nội dung và trải nghiệm học

| # | Tính năng | Udemy | Coursera | CodeLearn | Hệ thống đề xuất |
|---|---|:---:|:---:|:---:|:---:|
| 1 | Video bài giảng có ghi nhớ tiến độ, tùy chỉnh tốc độ | ✔ | ✔ | ◐ (nội dung dạng bài đọc + thực hành là chính) | ✔ (3) |
| 2 | Phụ đề / transcript | ✔ | ✔ | ✘ | ◐ (3 — có thể cắt giảm nếu trễ tiến độ) |
| 3 | Tìm kiếm, lọc theo danh mục/giá/đánh giá | ✔ | ✔ | ◐ (lọc theo kỹ năng, độ khó, chủ đề) | ✔ (2) |
| 4 | Lộ trình học có cấu trúc (learning path) | ◐ (Learning Plan, chủ yếu gói doanh nghiệp) | ✔ (Specialization, Professional Certificate) | ✔ | ◐ (ngoài phạm vi v1, xếp vào hướng phát triển) |
| 5 | Ghi chú theo mốc thời gian video | ✔ | ◐ | ✘ | ✔ (8) |
| 6 | Hỏi đáp theo bài học, upvote | ✔ | ✔ (diễn đàn) | ◐ (cộng đồng, blog) | ✔ (9) |
| 7 | Quiz trắc nghiệm tự động chấm | ✔ | ✔ | ✔ | ✔ (5) |
| 8 | Chứng chỉ hoàn thành | ✔ | ✔ (có kiểm định, tính phí) | ✔ (chứng nhận nội bộ) | ✔ (10 — PDF tự sinh, QR xác thực) |

### 3.2. Chấm mã nguồn tự động ★

| # | Tính năng | Udemy | Coursera | CodeLearn | Hệ thống đề xuất |
|---|---|:---:|:---:|:---:|:---:|
| 9 | Trình soạn thảo code nhúng trong bài học | ✔ | ✔ (lab, notebook) | ✔ | ✔ (4) |
| 10 | Chấm tự động theo test case | ✔ ("Run tests"/"Run query") | ✔ (autograder, AI-Graded Questions) | ✔ | ✔ ★ (4) |
| 11 | Số ngôn ngữ hỗ trợ chấm | ✔ 22 ngôn ngữ/môi trường | ◐ (tùy khóa học và đối tác) | ✔ 19 khóa ngôn ngữ | ◐ v1 chỉ Python, kiến trúc image per-language để mở rộng |
| 12 | Test case ẩn (chống lộ đáp án) | ◐ (không công bố chi tiết) | ◐ | ✔ (mô hình chấm thi đấu) | ✔ ★ (14) |
| 13 | Giới hạn tài nguyên CPU/RAM/thời gian, tắt mạng | ✘ (không công bố) | ✘ (không công bố) | ✘ (không công bố) | ✔ ★ — **thiết kế và đo đạc công khai trong báo cáo** |
| 14 | Trả kết quả realtime qua hàng đợi | ◐ | ◐ | ✔ (Real-time Challenge) | ✔ ★ (4 — Celery + Redis) |
| 15 | Thi đấu/contest có bảng xếp hạng | ✘ | ✘ | ✔ (Code War, xếp hạng theo kỹ năng) | ◐ (leaderboard XP ở tính năng 11, không có contest) |

> **Nhận xét:** cả ba nền tảng đều có chấm mã nguồn tự động, nhưng **cơ chế cô lập sandbox không được nền tảng nào công bố** — đây là hộp đen về mặt học thuật. Giá trị khoa học của đề tài không nằm ở việc "có chấm code", mà ở chỗ **thiết kế, chứng minh và đo đạc được tính an toàn của sandbox** (chống fork bomb, chặn truy cập mạng, chặn đọc file hệ thống) — nội dung sẽ trình bày ở Chương 3 và kiểm chứng ở Chương 5.

### 3.3. Tính năng AI ★

| # | Tính năng | Udemy | Coursera | CodeLearn | Hệ thống đề xuất |
|---|---|:---:|:---:|:---:|:---:|
| 16 | Trợ lý AI hỏi đáp trong bài học | ✔ (Udemy AI Assistant) | ✔ (Coursera Coach) | ◐ (gợi ý hướng sửa lỗi khi nộp bài) | ✔ ★ (6) |
| 17 | Câu trả lời có **trích dẫn nguồn** về bài giảng | ✘ (không công bố) | ◐ ("grounded in expert content", không nêu cơ chế trích dẫn) | ✘ | ✔ ★ (6 — RAG có trích nguồn, là tiêu chí gate của Phase 4) |
| 18 | Gợi ý khóa học cá nhân hóa | ◐ (công cụ gợi ý của AI Assistant **ngừng cung cấp sau 31/08/2026**) | ✔ | ✔ (phân tích hành vi học để đề xuất bài/lộ trình) | ✔ ★ (7 — hybrid: collaborative + content-based) |
| 19 | Công bố chỉ số đánh giá chất lượng gợi ý | ✘ | ◐ (công bố hiệu quả học tập của Coach: +9,5% tỉ lệ đạt quiz lần đầu, +11,6% bài học/giờ — không phải chỉ số recommender) | ✘ | ✔ ★ (precision@k, recall@k — bắt buộc trong Chương 5) |
| 20 | AI hỗ trợ giảng viên sinh đề/quiz | ◐ ("Generate with AI": sinh lời giải, test case, logic chấm — chỉ Python, C++, Java, Web và **chỉ khóa tiếng Anh**) | ✔ (AI-Graded Questions, Course Builder, AI-Assisted Grading) | ✘ | ✔ ★ (15 — sinh quiz từ nội dung bài giảng) |

> **Nhận xét:** khoảng trống rõ nhất không phải là "chưa nền tảng nào có AI" — cả Udemy và Coursera đều đã triển khai trợ lý AI ở quy mô lớn. Khoảng trống nằm ở ba điểm: (a) các tính năng AI mạnh nhất bị khóa sau **gói doanh nghiệp** hoặc **giới hạn ngôn ngữ tiếng Anh**; (b) **cơ chế bên trong không được công bố**, không thể tái lập trong môi trường học thuật; (c) nền tảng nội địa (CodeLearn) mạnh về chấm bài nhưng **chưa có trợ lý RAG trên nội dung khóa học**. Đề tài định vị vào giao điểm này: một kiến trúc **mở, tự triển khai được, chi phí thấp**, có số liệu đánh giá tái lập được.

### 3.4. Thương mại, gamification và quản trị

| # | Tính năng | Udemy | Coursera | CodeLearn | Hệ thống đề xuất |
|---|---|:---:|:---:|:---:|:---:|
| 21 | Giỏ hàng, thanh toán, mã giảm giá | ✔ | ✔ | ✘ (miễn phí) | ✔ (12 — VNPay/MoMo sandbox) |
| 22 | Cổng thanh toán nội địa Việt Nam | ◐ (thẻ quốc tế, ví điện tử tùy khu vực) | ◐ | — | ✔ (12 — **VNPay/MoMo**, lợi thế bản địa hóa) |
| 23 | Wishlist | ✔ | ✔ | ✘ | ◐ (12 — nằm trong danh sách cắt giảm) |
| 24 | Gamification: điểm, streak, bảng xếp hạng | ✘ | ◐ (huy hiệu) | ✔ (rank, xếp hạng theo kỹ năng) | ✔ (11) |
| 25 | Giảng viên tự tạo khóa học (curriculum, upload video) | ✔ | ◐ (chỉ đối tác được duyệt) | ✘ | ✔ (13) |
| 26 | Dashboard doanh thu/thống kê cho giảng viên | ✔ | ◐ | — | ✔ (16) |
| 27 | Quản trị viên duyệt khóa học, quản lý người dùng | ✔ | ✔ | ✔ | ✔ (18, 19, 20) |

## 4. Kết luận khảo sát — định vị đề tài

Tổng hợp ba bảng trên, có thể rút ra:

1. **Tập tính năng nền tảng (baseline) là bắt buộc, không phải điểm khác biệt.** Video có tiến độ, tìm kiếm, quiz, Q&A, chứng chỉ, thanh toán, dashboard quản trị đều xuất hiện ở cả ba nền tảng. Hệ thống đề xuất phải có đủ các tính năng này để "so sánh được", nhưng chúng không tạo ra giá trị khoa học cho khóa luận.

2. **Không nền tảng nào công bố thiết kế sandbox chấm bài.** Đây là khoảng trống học thuật rõ ràng nhất. Đóng góp của đề tài là mô tả đầy đủ kiến trúc cô lập, kèm **bảng thử nghiệm tấn công** (fork bomb, truy cập mạng, đọc file hệ thống) chứng minh các vector đều bị chặn.

3. **Không nền tảng nào có đồng thời ba điểm nhấn trên cùng một hệ thống mở.** Udemy và Coursera mạnh về AI nhưng đóng và tính phí theo gói doanh nghiệp; CodeLearn mạnh về chấm bài và gamification nhưng không có marketplace video, không có thanh toán, không có trợ lý RAG. Hệ thống đề xuất là nền tảng duy nhất trong nhóm khảo sát kết hợp: **marketplace khóa học video + chấm mã nguồn trong sandbox + recommender lai + chatbot RAG có trích nguồn**, triển khai bằng Docker Compose trên một VPS chi phí thấp.

4. **Lợi thế bản địa hóa có thể đo được:** giao diện và nội dung tiếng Việt, thanh toán qua VNPay/MoMo — trong khi tính năng AI của Udemy hiện giới hạn ở khóa học tiếng Anh.

> Ba kết luận (2), (3), (4) là căn cứ trực tiếp cho phần "Tính mới và đóng góp của đề tài" ở Chương 1.

## 5. Hạn chế của khảo sát

Cần nêu rõ trong báo cáo để bảo đảm tính khách quan:

- Khảo sát dựa trên **tài liệu công bố công khai**, không dựa trên tài khoản trả phí hay gói doanh nghiệp; do đó các ô đánh dấu ✘ nên hiểu là **"không công bố"** chứ không khẳng định "chắc chắn không có".
- Các nền tảng thương mại thay đổi tính năng liên tục (ví dụ: công cụ gợi ý của Udemy AI Assistant ngừng cung cấp sau 31/08/2026). Bảng so sánh phản ánh hiện trạng tại **19/08/2026** và cần ghi rõ mốc thời gian này khi trích dẫn.
- Một số tính năng AI của Coursera (AI-Graded Questions, AI-Assisted Grading, AI-Powered Peer Review) đang ở giai đoạn cung cấp giới hạn cho một số đối tác và khách hàng doanh nghiệp, chưa mở rộng đại trà.
- Không so sánh được **hiệu năng thực tế** (thời gian chấm bài, độ chính xác gợi ý) do các nền tảng không công bố số liệu; đề tài chỉ có thể tự đo trên hệ thống của mình và trình bày phương pháp đo để người khác tái lập.

## 6. Nguồn tham khảo

Truy cập ngày 19/08/2026:

1. [Learning With Coding Exercises — Udemy Support](https://support.udemy.com/hc/en-us/articles/229606768-Learning-With-Coding-Exercises)
2. [How to create a coding exercise — Udemy Support](https://support.udemy.com/hc/en-us/articles/115002883587-How-to-create-a-coding-exercise)
3. [Udemy's AI Tools: Instructor Supported Languages — Udemy Support](https://support.udemy.com/hc/en-us/articles/34467211373591-Udemy-s-AI-Tools-Instructor-Supported-Languages)
4. [How to access and use the Udemy AI Assistant — Udemy Business Support](https://business-support.udemy.com/hc/en-us/articles/27096117008279-How-to-access-and-use-the-Udemy-AI-Assistant)
5. [New AI-powered innovations on Coursera — Coursera Blog](https://blog.coursera.org/new-ai-powered-innovations-on-coursera/)
6. [Coursera launches Academic Integrity features — Coursera Blog](https://blog.coursera.org/coursera-launches-academic-integrity-features-to-help-universities-verify-learning-in-an-age-of-ai-assisted-cheating/)
7. [Announcing AI-powered capabilities: Coursera Coach for educators — Coursera Blog](https://blog.coursera.org/announcing-ai-powered-capabilities-enabling-educators-to-use-coursera-coach-to-deliver-interactive-personalized-instruction)
8. [CodeLearn.io — Trang chủ](https://codelearn.io/)
9. [CodeLearn — Vì một thế hệ Việt làm chủ tư duy lập trình — FPT IS](https://fpt-is.com/codelearn-vi-mot-the-he-viet-lam-chu-tu-duy-lap-trinh/)
10. [Nền tảng học lập trình CodeLearn nhận giải Sao Khuê — VnExpress](https://vnexpress.net/nen-tang-hoc-lap-trinh-codelearn-nhan-giai-sao-khue-4102409.html)

---

## Việc còn lại của Chương 1

- [ ] Chụp ảnh màn hình minh họa (mỗi nền tảng 1–2 ảnh: màn hình chấm code, màn hình trợ lý AI) lưu vào thư mục này, đặt tên `screenshot-<nen-tang>-<noi-dung>.png`
- [ ] Chuyển mục 4 thành văn xuôi khi viết Chương 1 (bảng dùng làm phụ lục)
