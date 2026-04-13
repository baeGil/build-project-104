# Kế Hoạch V2 Cho AI Rà Soát Hợp Đồng Pháp Luật Việt Nam

`plan_v1.md` đã được cập nhật để phản ánh hướng triển khai thực tế thay cho bản mô tả ý tưởng ban đầu.

## Định vị giai đoạn 1

- Tập trung vào `Vietnamese legal retrieval + contract review engine`.
- Chưa ưu tiên quy chế nội bộ đại học vì chưa có corpus thật.
- Ưu tiên `accuracy + speed`, đặc biệt `retrieval + ranking p95 < 1s`.

## Kiến trúc chuẩn hóa

- Không dùng `full agentic loop` trên request path.
- Dùng `deterministic retrieval pipeline + lightweight planner + verifier`.
- `GraphRAG` chỉ là lớp augmentation cho câu hỏi khám phá nhiều bước.
- `Generation service` không được tự đi tìm luật; chỉ dùng `EvidencePack`.

## Phạm vi scaffold hiện tại

- Backend FastAPI với các endpoint:
  - `POST /api/v1/ingest/legal-corpus`
  - `POST /api/v1/review/contracts`
  - `POST /api/v1/chat/legal`
  - `GET /api/v1/citations/{node_id}`
- Types chính:
  - `LegalNode`
  - `QueryPlan`
  - `EvidencePack`
  - `ReviewFinding`
  - `ChatAnswer`
- Workspace:
  - `packages/ingestion`
  - `packages/retrieval`
  - `apps/review-api`
  - `apps/web-app`

## Pipeline hot path

1. `Clause parser` tách điều khoản.
2. `Query planner` chuẩn hóa typo/viết tắt, mở rộng synonym, phát hiện phủ định.
3. `Hybrid retrieval` chạy lexical + semantic song song.
4. `RRF fusion` lấy candidate nhỏ.
5. `Rerank` và tiêm `parent + sibling exceptions + linked amendments`.
6. `Verifier` chấm `entailed / contradicted / partially_supported / no_reference`.
7. `Generator` sinh rationale, citation, revision, negotiation note, diff.

## Dataset giai đoạn hiện tại

- Dùng `th1nhng0/vietnamese-legal-documents` làm nguồn định hướng.
- Scaffold local đang dùng `data/samples/legal_nodes.json` để chạy offline.
- Cần bổ sung pipeline đồng bộ `vbpl.vn`, hợp đồng công khai và bộ clause synthetic.

## Việc tiếp theo sau scaffold

- Bind Qdrant/OpenSearch thật cho retrieval.
- Thêm real reranker như ColBERTv2 hoặc cross-encoder.
- Viết bộ benchmark retrieval/review/latency/safety.
- Thêm OCR, redaction, external LLM adapter cho reasoning/rewrite.
