# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Minh Cương |
| MSSV | 2A202602825 |
| Khóa/Lớp | K4 |
| Tên nhóm | GroupXX-CSUI202 |
| Vai trò chính | Pipeline Integrator |
| Repository | https://github.com/anhtri04/K4A-DAY10-GroupXX-CSUI202 |
| Ngày hoàn thành | 2026-09-25 |

## 2. Phạm vi công việc

- Tích hợp pipeline baseline từ raw snapshot đến cleaning, ChromaDB, evaluation và báo cáo.
- Tích hợp luồng corruption, quality/freshness monitoring, repair từ raw và đối chiếu ba trạng thái.
- Kiểm tra các artifact, collection ChromaDB và tính idempotent của repair.

Các module và artifact chính:

| Phần việc | File/artifact |
| --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py` |
| Corruption và repair orchestration | `src/pipelines/corruption_flow.py` |
| Cấu hình và tiện ích ghi artifact | `src/core/` |
| Báo cáo baseline | `data/reports/phase1_report.md` |
| Báo cáo so sánh | `data/reports/corruption_report.md` |

## 3. Kết quả xác minh

Hai entrypoint đã chạy với exit code 0:

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
```

| Metric/signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Retrieval hit rate | 1.0000 | 0.5000 | 1.0000 |
| Mean token F1 | 1.0000 | 0.7788 | 1.0000 |
| Judge accuracy | 1.0000 | 0.8000 | 1.0000 |
| Quality gate | Pass | Fail | Pass |
| Freshness SLA | Pass | Fail | Pass |
| Stale ratio | 0.0417 | 0.3333 | 0.0417 |

Repair được chạy lặp lại và cho cùng hash ở `papers_clean_repaired.json` và `repaired_metrics.json`. Kết quả này chứng minh dữ liệu được tái tạo ổn định từ raw snapshot thay vì vá trực tiếp dataset bị lỗi.

## 4. Hiểu biết về luồng end-to-end

Crossref metadata được bảo toàn ở tầng raw, sau đó chuẩn hóa thành dataframe có `paper_id`, `age_days` và `text_for_embedding`. Dữ liệu sạch chỉ được index sau khi vượt qua Quality Gate và Freshness SLA. Một test set cố định gồm 10 câu được dùng chung cho baseline, corrupted và repaired để phép so sánh không bị thay đổi đề đánh giá.

Corruption suite tạo sáu dạng lỗi: mất bản ghi mới, summary rỗng, nhiễu văn bản, title bị cắt, ngày stale và bản ghi trùng. Great Expectations phát hiện vi phạm completeness/uniqueness/length, còn freshness monitoring phát hiện tỷ lệ dữ liệu cũ vượt 25%. Repair đọc lại raw snapshot, làm sạch và xây collection mới nên không kế thừa trạng thái hỏng.

## 5. Bằng chứng bàn giao

- `data/results/baseline_metrics.json`
- `data/results/corrupted_metrics.json`
- `data/results/repaired_metrics.json`
- `data/results/corruption_log.json`
- `data/quality/`
- `data/reports/phase1_report.md`
- `data/reports/corruption_report.md`

Không có API key hoặc file `.env` trong bài nộp.
