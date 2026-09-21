# Đánh giá recommender trên tập held-out — precision@k, recall@k

- Ngày chạy: 21/09/2026 09:51 UTC · stack dev · chỉ đọc CSDL, không gọi Gemini · 4.1 s
- Dữ liệu: 190 tương tác · 48 học viên (3 khóa: 13, 4 khóa: 24, 5 khóa: 11) · 24 khóa trong catalogue · 24 vector `gemini-embedding-001` · dấu vân tay `af1231c3dd44`
- Warm: 5 fold cắt theo từng học viên × 5 lần xáo (hạt giống 20261101…20261105) · cold-start: 24 lần, mỗi lần một khóa
- Mỗi nửa đưa cho blend 5 ứng viên (`FUSION_DEPTH`), như job hằng đêm · RRF k = 60, trọng số collaborative 1 : content 1
- Tái tạo (từ thư mục gốc repo, sau `scripts.seed`, `scripts.seed_interactions`, `scripts.rebuild_course_embeddings`):
  `docker compose -f infra/docker-compose.yml exec -T backend python -m scripts.eval_recommender > docs/report/assets/phase-4/recommender-eval.md`

**Dữ liệu là giả lập** (`scripts/seed_interactions.py`: 4 cụm sở thích, hạt giống cố định). Con số đo được là khả năng khôi phục một cấu trúc đã biết là có, không phải bằng chứng người học thật thấy gợi ý hữu ích.

Precision@k chia cho k kể cả khi mô hình trả ít hơn k khóa — chỗ trống là chỗ trượt. Recall@k chia cho số khóa bị giấu. Mỗi ca kiểm là một học viên trong một fold; mọi ca nặng như nhau. Ô có ngoặc: trung bình (thấp nhất–cao nhất) qua các lần xáo.

## 1. Warm — giấu tương tác của người đã có lịch sử

Mỗi tương tác bị giấu đúng một lần; mô hình khớp lại trên phần còn lại. Số ca kiểm mỗi lần xáo: 190.

| Mô hình | P@3 | R@3 | P@4 | R@4 | P@5 | R@5 | P@8 | R@8 | P@10 | R@10 |
|---|---|---|---|---|---|---|---|---|---|---|
| *Trần lý thuyết* (xếp hạng hoàn hảo) | 0,333 | 1,000 | 0,250 | 1,000 | 0,200 | 1,000 | 0,125 | 1,000 | 0,100 | 1,000 |
| Ngẫu nhiên (kỳ vọng) | 0,048 (0,048–0,048) | 0,144 (0,144–0,144) | 0,048 (0,048–0,048) | 0,191 (0,191–0,191) | 0,048 (0,048–0,048) | 0,239 (0,239–0,239) | 0,048 (0,048–0,048) | 0,383 (0,383–0,383) | 0,048 (0,048–0,048) | 0,479 (0,479–0,479) |
| Phổ biến (đếm trên tập train) | 0,037 (0,030–0,044) | 0,112 (0,089–0,132) | 0,036 (0,032–0,038) | 0,143 (0,126–0,153) | 0,036 (0,029–0,043) | 0,178 (0,147–0,216) | 0,035 (0,032–0,039) | 0,280 (0,253–0,311) | 0,038 (0,036–0,041) | 0,383 (0,358–0,411) |
| Collaborative (item-based CF) | 0,257 (0,246–0,265) | 0,772 (0,737–0,795) | 0,217 (0,212–0,221) | 0,869 (0,847–0,884) | 0,178 (0,175–0,181) | 0,888 (0,874–0,905) | 0,114 (0,111–0,116) | 0,909 (0,884–0,926) | 0,092 (0,091–0,094) | 0,922 (0,905–0,937) |
| Content-based | 0,196 | 0,589 | 0,174 | 0,695 | 0,152 | 0,758 | 0,107 | 0,853 | 0,088 | 0,884 |
| Hybrid — trước 21/09 (độ sâu 20) | 0,254 (0,251–0,258) | 0,763 (0,753–0,774) | 0,209 (0,203–0,214) | 0,836 (0,811–0,858) | 0,173 (0,171–0,177) | 0,866 (0,853–0,884) | 0,114 (0,112–0,117) | 0,914 (0,895–0,937) | 0,092 (0,091–0,094) | 0,924 (0,911–0,937) |
| **Hybrid — cấu hình đang chạy** (độ sâu 5) | 0,248 (0,240–0,253) | 0,743 (0,721–0,758) | 0,209 (0,207–0,211) | 0,835 (0,826–0,842) | 0,177 (0,173–0,180) | 0,884 (0,863–0,900) | 0,115 (0,114–0,116) | 0,921 (0,916–0,932) | 0,092 (0,092–0,093) | 0,921 (0,916–0,932) |

## 2. Cold-start — ngày một khóa vừa xuất bản

Với từng khóa: gỡ mọi tương tác chạm tới nó, khớp lại, rồi hỏi những người từng học nó xem khóa ấy có lọt top-k không. Collaborative bằng 0 theo cấu tạo — khóa chưa ai học không đồng xuất hiện với gì cả. Số ca kiểm: 190.

| Mô hình | P@3 | R@3 | P@4 | R@4 | P@5 | R@5 | P@8 | R@8 | P@10 | R@10 |
|---|---|---|---|---|---|---|---|---|---|---|
| *Trần lý thuyết* (xếp hạng hoàn hảo) | 0,333 | 1,000 | 0,250 | 1,000 | 0,200 | 1,000 | 0,125 | 1,000 | 0,100 | 1,000 |
| Ngẫu nhiên (kỳ vọng) | 0,048 | 0,144 | 0,048 | 0,191 | 0,048 | 0,239 | 0,048 | 0,383 | 0,048 | 0,479 |
| Phổ biến (đếm trên tập train) | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 |
| Collaborative (item-based CF) | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 |
| Content-based | 0,196 | 0,589 | 0,174 | 0,695 | 0,152 | 0,758 | 0,107 | 0,853 | 0,088 | 0,884 |
| Hybrid — trước 21/09 (độ sâu 20) | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 | 0,003 | 0,026 | 0,011 | 0,105 |
| **Hybrid — cấu hình đang chạy** (độ sâu 5) | 0,054 | 0,163 | 0,116 | 0,463 | 0,125 | 0,626 | 0,095 | 0,758 | 0,076 | 0,758 |

## 3. Độ nhạy: độ sâu, trọng số, hằng số k

Độ sâu = số ứng viên mỗi nửa đưa cho blend (job hằng đêm dùng 5, trước 21/09 là 20). Các hàng độ sâu dùng trọng số 1 : 1 và k = 60. Chỉ recall; ở cả hai giao thức gần như mọi ca giấu đúng một khóa nên precision@k ≈ recall@k / k. Warm là trung bình qua các lần xáo. Đây là bản đồ đánh đổi, không phải cuộc tìm cấu hình thắng: dữ liệu được sinh từ chính các cụm mà nó được chấm theo.

| Cấu hình | warm R@3 | warm R@4 | warm R@5 | warm R@8 | warm R@10 | cold R@3 | cold R@4 | cold R@5 | cold R@8 | cold R@10 |
|---|---|---|---|---|---|---|---|---|---|---|
| độ sâu 2 | 0,615 | 0,663 | 0,663 | 0,663 | 0,663 | 0,395 | 0,432 | 0,432 | 0,432 | 0,432 |
| độ sâu 3 | 0,694 | 0,821 | 0,842 | 0,844 | 0,844 | 0,379 | 0,553 | 0,589 | 0,589 | 0,589 |
| độ sâu 4 | 0,745 | 0,823 | 0,886 | 0,903 | 0,903 | 0,274 | 0,537 | 0,626 | 0,695 | 0,695 |
| độ sâu 5 | 0,743 | 0,835 | 0,884 | 0,921 | 0,921 | 0,163 | 0,463 | 0,626 | 0,758 | 0,758 |
| độ sâu 6 | 0,760 | 0,836 | 0,880 | 0,926 | 0,927 | 0,116 | 0,368 | 0,595 | 0,774 | 0,816 |
| độ sâu 8 | 0,755 | 0,817 | 0,844 | 0,923 | 0,929 | 0,021 | 0,121 | 0,400 | 0,763 | 0,816 |
| độ sâu 10 | 0,763 | 0,828 | 0,844 | 0,916 | 0,934 | 0,000 | 0,016 | 0,111 | 0,705 | 0,816 |
| độ sâu 15 | 0,763 | 0,836 | 0,867 | 0,904 | 0,921 | 0,000 | 0,000 | 0,000 | 0,116 | 0,326 |
| độ sâu 20 | 0,763 | 0,836 | 0,866 | 0,914 | 0,924 | 0,000 | 0,000 | 0,000 | 0,026 | 0,105 |
| độ sâu 5 · CF 2 : content 1 · k = 60 | 0,764 | 0,867 | 0,888 | 0,921 | 0,921 | 0,000 | 0,000 | 0,000 | 0,758 | 0,758 |
| độ sâu 5 · CF 1 : content 2 · k = 60 | 0,702 | 0,743 | 0,758 | 0,921 | 0,921 | 0,226 | 0,595 | 0,758 | 0,758 | 0,758 |
| độ sâu 5 · CF 1 : content 1 · k = 10 | 0,743 | 0,835 | 0,884 | 0,921 | 0,921 | 0,163 | 0,463 | 0,626 | 0,758 | 0,758 |

