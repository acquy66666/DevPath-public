# Thiết kế: cấp bậc giảng viên, hoa hồng và thống kê tài chính

> Yêu cầu của user ngày 20/10/2026 (tạm dừng các task đang theo tiến độ để làm phần này). Tài liệu ghi lại **ý tưởng thô của user**, **những gì ba subagent nghiên cứu tìm được** về cách các nền tảng lớn làm, và **những quyết định đã chốt khi hiện thực**. Các chỗ là giả định của Claude, chưa được user xác nhận, có đánh dấu **[Giả định]**.

## 1. Yêu cầu gốc

1. **Giảng viên chỉ thấy số liệu về khóa học và học viên**, không thấy bất kỳ con số nào liên quan tới tiền: không doanh thu theo ngày/tháng/năm, không doanh thu của giảng viên khác. Danh mục chỉ số phải đầy đủ, chi tiết.
2. Từ các số liệu đó, giảng viên được **xếp cấp độ** (tên tự đặt). Cấp càng cao thì **hoa hồng (commission) càng tốt**.
3. **Admin xét duyệt nâng cấp** cho giảng viên, dựa trên số học viên và doanh thu của họ.
4. Trang thống kê **của admin** mới thấy doanh thu:
   - doanh thu tổng thể theo các mốc thời gian, và của từng giảng viên;
   - bảng xếp hạng riêng cho từng khoản mục;
   - tính hoa hồng cho từng giảng viên, có tính năng **lập "check bill" (bảng kê)** cho từng người;
   - trang **lợi nhuận giữ lại** sau khi trừ chi phí.
5. **Mọi trang đều xuất được Excel.**
6. Gọi subagent nghiên cứu mô hình thống kê của các trang web nổi tiếng để chọn phương án tốt nhất.

[Giả định] Câu "xếp hạng được học viên theo các cấp độ" được hiểu là xếp **giảng viên**, vì phần còn lại của yêu cầu nói về hoa hồng và admin nâng cấp *giáo viên*.

## 2. Nghiên cứu (20/10/2026, ba subagent song song)

### 2.1 Chỉ số cho giảng viên

- **Nguồn đã khảo sát:** Udemy (Performance: Overview, Students, Reviews, Engagement, Traffic & conversion, practice test, coding exercise), Coursera, Open edX Aspects, Skillshare, LinkedIn Learning, Teachable, Thinkific/Kajabi, YouTube Studio và Unica.
- **Bốn nhóm số không dính tiền** mà nền tảng nào cũng có:
  - quy mô (học viên, ghi danh);
  - mức học (phút xem, retention, hoàn thành theo bài);
  - kết quả (phễu quiz/bài tập, tỉ lệ đạt);
  - hài lòng và tương tác (sao, nhận xét, Hỏi đáp).
- **Không nền tảng nào có bảng xếp hạng giảng viên** cho chính giảng viên. Họ chỉ cho so với chính mình (YouTube so với mức "typical" của kênh) hoặc với số gộp theo chủ đề (Udemy Marketplace Insights).
  - → Trang giảng viên **không có bảng xếp hạng**, chỉ so giữa các khóa của chính họ.
- **Chỉ số khó gian lận** là AC trên test ẩn, quiz có đồng hồ ở server, số ngày hoạt động và điểm sao gia quyền theo người mua thật.
  - **Dễ bị đẩy số:** ghi danh khóa 0đ, wishlist, tỉ lệ hoàn thành (vì hệ thống cho tự đánh dấu hoàn thành bài).
- **Rò rỉ tiền:** số lượt ghi danh *trả phí* nhân với giá công khai ≈ doanh thu.
  - → Không tách ghi danh theo nguồn trên trang giảng viên.
- **Đo được với dữ liệu hiện có:** khoảng 80% bộ chỉ số. **Không đo được** (ghi vào hướng phát triển):
  - lượt xem trang khóa học và nguồn traffic (chưa log);
  - phút xem thật và đường retention (`lesson_progress` chỉ giữ `last_position_s`);
  - thời gian đọc bài, thiết bị và quốc gia của học viên.

### 2.2 Phân cấp và tỉ lệ chia

- **Nguồn đã khảo sát:** Fiverr Seller Levels, Upwork (Rising Talent → Expert-Vetted, JSS), Envato, Udemy (37%/97% theo kênh), Skillshare, TPT, YouTube Partner, Twitch Plus, Shopee/Lazada, Apple/Google Small Business, Unica, Edumall.
- **Phần lớn không gắn tỉ lệ tiền vào cấp.** Fiverr, Upwork, Shopee và Udemy dùng cấp cho huy hiệu và hiển thị.
  - Chỉ Twitch (50 → 60 → 70%) và Envato kiểu cũ gắn tiền vào cấp, mà Envato đã bỏ từ 01/07/2026 vì quá tốn.
  - → Cần trần tỉ lệ và giữ biên ≥ 30% cho sàn.
- **Mẫu chung:**
  - điều kiện định lượng tính tự động, cấp cao nhất xét tay (Fiverr Top Rated, Upwork Expert-Vetted, YouTube);
  - cửa sổ trượt 12 tháng;
  - đếm khách không trùng;
  - ân hạn trước khi hạ cấp.
- **Đổi tỉ lệ giữa chừng thì không áp ngược.** Apple, Envato, Udemy và Upwork đều áp mức mới cho doanh số từ đó về sau.
  - → **Chụp tỉ lệ vào từng dòng bán**, không bao giờ tính lại.

### 2.3 Tài chính, bảng kê, P&L, thuế

- **Nguồn đã khảo sát:** Udemy payout, Stripe Connect, App Store Connect, Shopify Partners, Gumroad, Teachable, Shopee/Lazada.
- **Chia trên tiền thực thu** (Udemy gọi là "net amount").
- **Kỳ và ngưỡng trả:**
  - kỳ theo tháng;
  - có ngưỡng tối thiểu, chưa đủ thì dồn sang kỳ sau; Udemy trả hết ở kỳ tháng 12.
- **Bảng kê đã chốt thì không sửa.** Sai sót sửa bằng dòng điều chỉnh ở kỳ sau, như credit note của Stripe hay dòng `R` âm của Apple.
- **Phí cổng thanh toán:** biểu phí công khai tìm được là của Nam A Bank cho đơn vị chấp nhận thanh toán qua VNPAY (15/06/2026): thẻ hoặc tài khoản nội địa **0,8%**. Phí thật nằm trong hợp đồng merchant.
- **Thuế TNCN:**
  - **từ 01/07/2026, ngưỡng khấu trừ 10% là 5 triệu đồng/lần** (NĐ 253/2026; trước đó là 2 triệu theo TT 111/2013);
  - cách phân loại khoản chia doanh thu (tiền công, thu nhập kinh doanh hay bản quyền) **chưa xác minh được**, cần kế toán.
- **Thông lệ xuất Excel:**
  - sheet đầu là tóm tắt (kỳ báo cáo, thời điểm xuất), sheet cuối là định nghĩa;
  - tiền lưu dạng số kèm định dạng;
  - chặn formula injection.

Báo cáo đầy đủ của ba subagent (có URL nguồn) nằm trong transcript phiên 20/10/2026. Nếu cần trích trong báo cáo khóa luận thì lấy các URL ở đó.

## 3. Cấp bậc giảng viên

Năm cấp, đặt tên theo chủ đề "con đường" của DevPath (bộ tên A trong nghiên cứu):

| Hạng | Cấp | Giảng viên nhận | Học viên trả phí | Doanh thu 365 ngày | Đánh giá (số đánh giá) | Hoàn thành | Trả lời Hỏi đáp ≤ 48 giờ | Khóa đang bán | Tháng hoạt động |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Khởi hành | **50%** | — | — | — | — | — | — | — |
| 2 | Dẫn đường | **55%** | ≥ 20 | ≥ 5 tr | ≥ 4,0 (5) | — | ≥ 60% | ≥ 1 | ≥ 2 |
| 3 | Mở lối | **60%** | ≥ 100 | ≥ 30 tr | ≥ 4,3 (20) | ≥ 10% | ≥ 75% | ≥ 1 | ≥ 6 |
| 4 | Tiên phong | **65%** | ≥ 400 | ≥ 150 tr | ≥ 4,5 (60) | ≥ 15% | ≥ 85% | ≥ 1 | ≥ 12 |
| 5 | Huyền thoại | **70%** | ≥ 1.500 | ≥ 500 tr | ≥ 4,6 (150) | ≥ 20% | ≥ 90% | ≥ 2 | ≥ 24 |

**Vì sao 50 → 70%:**

- **Sàn 50%** bằng Envato hiện nay và Twitch cơ bản, và cao hơn 37% của Udemy để hút giảng viên cho một sàn còn nhỏ.
- **Trần 70%** bằng Twitch Plus L2, giữ cho sàn ≥ 30% để trả phí VNPay, hạ tầng, Gemini và sandbox chấm bài.
- **Mức 90–97%** của Unica/Udemy là cho kênh "giảng viên tự mang khách tới". Kênh này chưa có ở đây; nếu làm thì làm thành một kênh riêng ở giai đoạn sau, không trộn vào cấp.

**Định nghĩa từng chỉ số** (`backend/app/services/instructor_tiers.py`), chọn để khó gian lận bằng tài khoản phụ:

- **Học viên trả phí:**
  - người mua khác nhau trả ≥ 30% giá niêm yết và ≥ 10.000đ, qua cổng thanh toán;
  - không tính đơn 0đ (mã 100%) và tài khoản bị khóa.
- **Doanh thu 365 ngày:** Σ(`unit_price − discount`) của các đơn đã trả.
- **Đánh giá:**
  - trung bình Bayes, (tổng sao + 4,0 × 10) / (số đánh giá + 10);
  - chỉ tính đánh giá của **người đã mua**.
- **Hoàn thành:** tính trên các lượt ghi danh trả phí đã quá 30 ngày.
- **Hỏi đáp:**
  - phạm vi là câu hỏi của học viên trong 90 ngày, đã quá 48 giờ;
  - đo phần trăm được giảng viên trả lời trong 48 giờ;
  - dưới 5 câu thì coi là đạt.
- **Điều kiện chung từ cấp 2:**
  - tài khoản không bị khóa;
  - không có khóa học bị gỡ do báo cáo vi phạm trong 90 ngày.

**Quy trình:**

- **Hệ thống chỉ đề xuất.** Trang admin "Cấp giảng viên" tính số liệu tại chỗ, không có job hay snapshot. Cấp đề xuất là cấp cao nhất mà mọi tiêu chí đều đạt.
- **Admin quyết định:**
  - chọn cấp và ghi lý do (bắt buộc);
  - quyết định được lưu vào `instructor_tier_changes` kèm ảnh chụp số liệu lúc quyết định;
  - giảng viên nhận thông báo `instructor_tier_changed`;
  - tỉ lệ mới áp dụng cho **đơn thanh toán từ lúc đó**.
- **Ngưỡng duy trì thấp hơn ngưỡng vào**, để giảng viên không nhảy cấp lên xuống quanh một mốc:
  - 80% với học viên và doanh thu;
  - −0,2 sao với đánh giá;
  - −10 điểm phần trăm với hai tỉ lệ.
- **Tụt dưới ngưỡng duy trì chỉ gắn cờ** cho admin, không tự hạ cấp.
- **Hai gợi ý cho admin**, chỉ cảnh báo, không chặn:
  - "vừa đổi cấp < 6 tháng";
  - "đề xuất vượt cấp lên Huyền thoại".
- **[Giả định]** Bỏ qua celery beat xét hằng tháng và hàng đợi đề xuất `pending` mà nghiên cứu gợi ý. Với vài giảng viên, danh sách tính tại chỗ là đủ, và giữ được nguyên tắc "admin là người xét".
- **Tỉ lệ chốt vào từng dòng bán:**
  - `order_items.instructor_share_rate` được ghi trong `orders._deliver`, nơi chung cho IPN và đơn 0đ;
  - admin sửa tỉ lệ của một cấp thì chỉ ảnh hưởng đơn bán sau đó.

**Giảng viên thấy gì về cấp của mình** (`GET /instructor/tier`, trang `/giang-day/cap-bac`):

- cấp hiện tại và tỉ lệ; bậc thang cùng tỉ lệ từng cấp (mọi nền tảng khảo sát đều công khai tỉ lệ);
- tiến độ tới cấp kế tiếp:
  - tiêu chí không dính tiền: hiện giá trị và ngưỡng;
  - **"Học viên trả phí" và "Doanh thu 12 tháng": chỉ hiện Đạt / Chưa đạt**, không có số;
- lịch sử quyết định kèm lý do của admin.

## 4. Trang thống kê của giảng viên (không có tiền)

`/giang-day/thong-ke`, các kỳ 7 ngày / 30 ngày / 90 ngày / 12 tháng, giờ Việt Nam. Mọi ô so với kỳ ngay trước.

| Nhóm | Chỉ số |
|---|---|
| Tổng quan theo kỳ | ghi danh mới · học viên mới (lượt đầu tiên với giảng viên này) · học viên hoạt động · bài học hoàn thành · lượt hoàn thành khóa · đánh giá mới (+ điểm TB) · câu hỏi mới · lượt thêm vào yêu thích; biểu đồ theo ngày/tháng |
| Từ trước tới nay | tổng học viên · tổng lượt ghi danh · khóa đang bán / tổng khóa · tỉ lệ bắt đầu học · tỉ lệ hoàn thành · tiến độ TB · số ngày trung vị để hoàn thành · điểm đánh giá · chứng chỉ đã cấp · câu hỏi chờ trả lời |
| Học tập | tỉ lệ bắt đầu học · tỉ lệ bỏ dở (chưa xong và 30 ngày không có dấu vết) · số ngày trung vị tới bài đầu tiên |
| Quiz | lượt nộp · số người làm · điểm trung vị · **đạt ngay lần đầu** · tỉ lệ hết giờ |
| Bài code | lượt nộp chấm thật · số người · **tỉ lệ giải được** (AC trên test ẩn) · số lần nộp trung vị tới AC · phân bố verdict (bỏ SE) |
| Đánh giá | phân bố 1–5 sao · % có nhận xét · đánh giá mới trong kỳ |
| Hỏi đáp | câu hỏi mới · % có giảng viên trả lời · giờ phản hồi trung vị · % trả lời trong 24 giờ · % đã giải quyết · tồn đọng |
| Quan tâm | lượt thêm yêu thích · đang trong yêu thích · yêu thích → ghi danh · đang nằm trong giỏ |
| Từng khóa | học viên · ghi danh mới · bắt đầu học · hoàn thành · tiến độ · đánh giá · câu hỏi chờ · yêu thích · quiz đạt lần đầu · code giải được |
| Từng bài (phễu) | đã mở · đã hoàn thành (% trên lượt ghi danh) · video đã xem TB · quiz đạt lần đầu · code giải được · câu hỏi · ghi chú. Bậc rơi sâu nhất là bài cần xem lại |

**Không có số tiền nào**, kể cả lượt ghi danh tách trả phí/miễn phí. Test `test_nothing_an_instructor_reads_carries_money` duyệt mọi trường của mọi phản hồi, và kiểm cả tệp Excel.

## 5. Các trang tài chính của admin

| Trang | Nội dung | Excel |
|---|---|---|
| `/quan-tri` Tổng quan | Như trước (doanh thu toàn sàn, DAU, khóa hot) | Tổng quan · Theo thời gian · Khóa học hot |
| `/quan-tri/doanh-thu` | Doanh thu theo **giờ / ngày / tuần ISO / tháng / quý / năm** trong khoảng tự chọn, cho toàn sàn hoặc **một giảng viên**. Số liệu: đơn, dòng bán, người mua, giá niêm yết (GMV), giảm giá, học viên trả, hoa hồng giảng viên, phần sàn giữ; so với khoảng cùng độ dài ngay trước. Kèm bảng theo giảng viên (cấp, tỉ trọng) và theo khóa | Tóm tắt · Theo mốc · Theo giảng viên · Theo khóa học · Dòng bán · Định nghĩa |
| `/quan-tri/xep-hang` | 17 bảng xếp hạng, mỗi khoản mục một bảng, đồng hạng kiểu thi đấu (1, 2, 2, 4), kèm giá trị kỳ trước. **Giảng viên:** doanh thu, hoa hồng, học viên mới, lượt bán, đánh giá Bayes, hoàn thành, thời gian trả lời Hỏi đáp. **Khóa:** doanh thu, lượt bán, ghi danh, đánh giá, yêu thích. **Mã giảm giá:** lượt dùng, tiền giảm, doanh thu mang về. **Danh mục:** doanh thu, ghi danh. Thêm độ tập trung: % doanh thu của top 1/5/10 giảng viên | Tóm tắt + mỗi bảng một sheet |
| `/quan-tri/cap-giang-vien` | Danh sách xét cấp: cấp hiện tại, cấp đề xuất, cờ, mọi chỉ số kể cả tiền, chi tiết từng tiêu chí. Nút đổi cấp (bắt buộc ghi lý do), lịch sử, sửa bậc thang | Xét cấp · Bậc thang |
| `/quan-tri/thanh-toan` | Số dư từng giảng viên: hoa hồng từ trước tới nay, chưa lập bảng kê, nháp, đã chốt chưa chi, đã chi, thuế. Lập bảng kê theo tháng; danh sách bảng kê | Số dư giảng viên · Bảng kê |
| `/quan-tri/thanh-toan/[id]` | **Bảng kê (check bill)** một giảng viên: phần đầu, từng dòng bán, các nút chốt / ghi nhận đã chi (mã chuyển khoản) / hủy (lý do) / xóa nháp; in được | Bảng kê · Dòng bán · Định nghĩa |
| `/quan-tri/loi-nhuan` | Lãi lỗ theo tháng hoặc quý của một năm, kèm nhập và sửa chi phí | Lãi lỗ · Tỉ suất · Chi phí · Giả định (và tệp riêng cho danh sách chi phí) |

### Công thức (`backend/app/services/finance.py`)

```
học viên trả        = unit_price − discount                 (tổng các dòng = orders.total)
hoa hồng giảng viên = floor(học viên trả × tỉ lệ đã chốt)    làm tròn xuống tới đồng
phần sàn giữ        = học viên trả − hoa hồng giảng viên
```

- **[Giả định] Mã giảm giá do hai bên cùng chịu theo tỉ lệ.** Hoa hồng tính trên tiền thực thu, giống "net amount" của Udemy.
- **[Giả định] Phí cổng thanh toán do sàn chịu**, trừ trong phần sàn giữ, không trừ trước khi chia. Lý do: VNPay ở đây là IPN giả lập, đơn không lưu phí thật. Khi có phí thật theo đơn, có thể đổi sang "trừ phí trước khi chia" như Udemy (xem §8).

### Bảng kê (`backend/app/services/payouts.py`)

- **Lập cho một tháng đã qua.** Gồm mọi dòng bán đã trả, > 0đ, trước cuối tháng và chưa nằm trên bảng kê nào. Tháng chưa lập được dồn sang bảng kê sau; bảng kê ghi rõ số dòng tồn từ kỳ trước.
- **Ngưỡng chi tối thiểu 200.000đ.** Dưới ngưỡng thì dồn kỳ, trừ tháng 12 (trả hết, như Udemy).
- **Thuế TNCN ước tính** 10% khi một lần chi ≥ 5.000.000đ.
  - Admin tắt được trên bản nháp, ví dụ khi giảng viên đã nộp mẫu 08/CK-TNCN.
  - Bảng kê ghi rõ đây là ước tính cần kế toán xác nhận.
- **Vòng đời:**
  - nháp: sửa và xóa được;
  - đã chốt: khóa số;
  - đã chi: có mã chuyển khoản; là trạng thái cuối;
  - hủy: được từ nháp hoặc đã chốt, bắt buộc lý do; các dòng bán quay về hàng chờ.
- **Mỗi dòng bán nằm trên tối đa một bảng kê**, có unique index đảm bảo.
- **Dòng bảng kê là bản chép**, nên in lại năm sau vẫn đúng số đã chi.

### Lãi lỗ (`backend/app/services/profit.py`)

Ghi nhận theo ngày đơn được thanh toán (dồn tích), trình bày dạng doanh thu gộp như Udemy:

```
GMV (giá niêm yết) − giảm giá = học viên trả
− hoa hồng giảng viên         = doanh thu sàn          take rate = doanh thu sàn / GMV
− phí cổng thanh toán (ước tính 0,8% trên đơn qua VNPay)
− chi phí vận hành (admin nhập: hạ tầng, API AI, phí cổng điều chỉnh, marketing, nhân sự, khác)
= lợi nhuận trước thuế − thuế (admin nhập) = lợi nhuận giữ lại
```

Có ba tỉ suất: take rate, biên gộp (sau phí cổng) và biên lợi nhuận giữ lại.

## 6. Xuất Excel (`backend/app/services/excel.py`, `exports.py`)

- **Một bộ dựng chung cho mọi trang.** Tệp Excel dùng **đúng** kết quả service mà trang đang hiển thị: không tự tính số nào riêng, và tệp của giảng viên không thể có cột tiền.
- **Đầu mỗi sheet:**
  - phần mở đầu gồm tên báo cáo, kỳ, thời điểm xuất (giờ Việt Nam);
  - hàng tiêu đề in đậm, đóng băng, có bộ lọc.
- **Định dạng ô:**
  - tiền là **số** với định dạng `#,##0 "₫"` (vẫn cộng được);
  - tỉ lệ là phân số hiển thị `0.0%`;
  - thời gian là giờ Việt Nam.
- **Chữ do người dùng nhập luôn là ô chữ.** Tựa khóa học `=HYPERLINK(...)` không bao giờ thành công thức; có test kiểm.
- **Tên tệp:** `devpath_<trang>_<từ>_<đến>.xlsx`. Header có `filename*` UTF-8.

## 7. API

| Đối tượng | Route |
|---|---|
| Giảng viên | `GET /instructor/stats/overview` · `/insights` · `/courses` · `/courses/{id}/lessons` · `/export.xlsx` · `/courses/{id}/lessons/export.xlsx` · `GET /instructor/tier` |
| Admin | `GET /admin/finance/revenue` (+`/breakdown`, `/export.xlsx`) · `GET /admin/finance/rankings` (+`/export.xlsx`) · `GET/PATCH /admin/tiers` · `GET /admin/instructor-tiers` (+`/export.xlsx`, `/{id}`, `/{id}/history`) · `POST /admin/instructor-tiers/{id}` · `GET /admin/payouts/balances` · `GET/POST /admin/payouts/statements` · `GET/PATCH/DELETE /admin/payouts/statements/{id}` (+`/confirm`, `/pay`, `/void`, `/export.xlsx`) · `GET /admin/payouts/export.xlsx` · `GET /admin/finance/profit` (+`/export.xlsx`) · `GET/POST /admin/expenses` (+`/export.xlsx`), `PATCH/DELETE /admin/expenses/{id}` · `GET /admin/stats/export.xlsx` |

## 8. Chưa làm — hướng phát triển

- **Ghi lượt xem trang khóa học** (bảng sự kiện) để có phễu "khách → ghi danh" và nguồn traffic như Udemy Traffic & conversion.
- **Đo phút xem thật:** cộng dồn `watched_s` có chặn trần theo mỗi heartbeat, hoặc bitmap các đoạn 10 giây, để có retention.
- **Lưu `orders.gateway_fee` thật lúc IPN**, theo bảng phí có ngày hiệu lực (`vnp_CardType`, `vnp_BankCode`), và chia hoa hồng trên số tiền sau phí.
- **Thêm `coupons.cost_bearer`** (`shared`/`platform`/`instructor`), khi giảng viên được tự tạo mã.
- **Hoàn tiền:** bút toán âm theo đúng tỉ lệ đã chốt, đưa vào bảng kê kỳ sau dưới dạng dòng điều chỉnh, và giữ tiền 30 ngày trước khi trả.
- **Hồ sơ thuế của giảng viên** (`withholding_mode`, cam kết 08/CK-TNCN) và chứng từ khấu trừ điện tử (NĐ 254/2026).
- **Chi phí định kỳ tự sinh** đầu tháng; khóa sổ tháng đã đóng.
- **Snapshot số liệu hằng tháng** để vẽ lịch sử chỉ số theo cấp.
