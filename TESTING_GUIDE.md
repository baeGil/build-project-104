# 🧪 Hướng Dẫn Test Full-Stack: Legal Contract Review System

## 📋 Mục Lục
1. [Chuẩn Bị](#1-chuẩn-bị)
2. [Khởi Động Hệ Thống](#2-khởi-động-hệ-thống)
3. [Test Contract Review](#3-test-contract-review)
4. [Test Citations](#4-test-citations)
5. [Test Neo4j Graph](#5-test-neo4j-graph)
6. [Test Chat Legal](#6-test-chat-legal)
7. [Kiểm Tra Kết Quả](#7-kiểm-tra-kết-quả)

---

## 1. Chuẩn Bị

### 1.1 Kiểm Tra Database

```bash
# Kiểm tra PostgreSQL
cd "/Users/AI/Vinuni/build project qoder"
uv run python -c "
import asyncio
import asyncpg

async def check():
    pool = await asyncpg.create_pool('postgresql://postgres:postgres@localhost:5432/legal_review')
    async with pool.acquire() as conn:
        count = await conn.fetchval('SELECT COUNT(*) FROM legal_documents')
        print(f'✅ PostgreSQL: {count} documents')
    await pool.close()

asyncio.run(check())
"
```

**Expected Output:**
```
✅ PostgreSQL: 2021 documents
```

### 1.2 Kiểm Tra Services

```bash
# Kiểm tra Docker containers
docker ps

# Bạn sẽ thấy:
# - qdrant:6333
# - neo4j:7474, 7687
# - opensearch:9200 (nếu có)
```

---

## 2. Khởi Động Hệ Thống

### 2.1 Start Backend

```bash
cd "/Users/AI/Vinuni/build project qoder"

# Terminal 1 - Backend API
uv run uvicorn apps.review_api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### 2.2 Start Frontend

```bash
# Terminal 2 - Next.js Frontend
cd "/Users/AI/Vinuni/build project qoder/apps/web-app"
npm run dev
```

**Expected Output:**
```
▲ Next.js 14.x.x
- Local:   http://localhost:3000
✓ Ready in x.xs
```

### 2.3 Verify Health Check

Open browser: http://localhost:8000/api/v1/health

**Expected Response:**
```json
{
  "status": "ok",
  "services": {
    "postgresql": "connected",
    "qdrant": "connected",
    "neo4j": "connected"
  }
}
```

---

## 3. Test Contract Review

### 3.1 Upload Test Contract

1. Open browser: **http://localhost:3000/review**

2. Click **"Load Sample"** hoặc copy-paste nội dung từ:
   ```
   test contracts/comprehensive_test_contract.txt
   ```

3. Click **"Review Contract"**

### 3.2 Quan Sát Streaming Progress

Bạn sẽ thấy progress bar với các phases:

```
🔍 Đang phân tích hợp đồng...
⚙️  Đang xử lý 13 điều khoản...
  ✅ Điều 1: Phù hợp (confidence: 85%)
  ⚠️  Điều 6: Cảnh báo rủi ro TRUNG BÌNH
  ❌ Điều 9: Rủi ro CAO - Mâu thuẫn với luật
```

### 3.3 Kiểm Tra Results

Sau khi review xong, bạn sẽ thấy:

#### A. Summary Section
- ✅ Tổng số điều khoản: 13
- ✅ Risk breakdown:
  - 🔴 High: 2-3 clauses
  - 🟡 Medium: 3-4 clauses  
  - 🟢 Low: 4-5 clauses
  - ⚪ None: 2-3 clauses

#### B. Detailed Findings

**Click vào từng finding để expand:**

**Điều 1 - Phạm Vi Công Việc:**
- ✅ Verification: `entailed` (phù hợp)
- ✅ Confidence: ~85%
- ✅ Risk: `low` hoặc `none`
- ✅ Citations: Luật Đầu tư 2020, Luật Doanh nghiệp 2020

**Điều 6 - Chuyển Nhượng Đất Đai:**
- ⚠️ Verification: `partially_supported`
- ⚠️ Confidence: ~70%
- ⚠️ Risk: `medium`
- ⚠️ Citations: Luật Đất đai 2024

**Điều 9 - Chấm Dứt Hợp Đồng:**
- ❌ Verification: `contradicted`
- ❌ Confidence: ~90%
- ❌ Risk: `high`
- ❌ Reason: Vi phạm quy định về đơn phương chấm dứt hợp đồng

#### C. Citations Panel

**Click vào bất kỳ citation nào:**

1. **Citation Panel mở ra bên phải**
2. Bạn sẽ thấy:
   - 📄 Document title
   - 📝 Quote preview (200 chars đầu)
   - 🔗 Law ID (VD: "61/2020/QH14")
   
3. **Click "Xem thêm"** button
   - ✅ Quote expand to full text
   - ✅ Shows complete legal provision

4. **Click vào citation card** (toàn bộ card)
   - ✅ Opens detailed citation panel
   - ✅ Shows hierarchy (nếu có trong Neo4j)
   - ✅ Shows related amendments
   - ✅ Shows citing articles

---

## 4. Test Citations

### 4.1 Citation Display

Trong kết quả review, test các scenarios:

#### Scenario 1: Citation với Quote Ngắn (< 150 chars)
- ✅ Hiển thị đầy đủ không bị cắt
- ✅ Không có "Xem thêm" button

#### Scenario 2: Citation với Quote Dài (> 150 chars)
- ✅ Hiển thị 150 chars đầu + "..."
- ✅ Có "▼ Xem thêm" button
- ✅ Click vào → Expand full quote
- ✅ Click "▲ Thu gọn" → Collapse lại

#### Scenario 3: Inline Citations trong Rationale
- ✅ Có numbered markers [1], [2], [3]
- ✅ Hover vào marker → Tooltip hiện preview (400 chars)
- ✅ Click vào marker → Mở citation panel

### 4.2 Citation Panel Details

Khi click vào citation, panel hiển thị:

```
┌─────────────────────────────────────────────┐
│  📄 Luật Đầu tư số 61/2020/QH14            │
├─────────────────────────────────────────────┤
│  "Điều 16. Thủ tục đầu tư                   │
│   1. Nhà đầu tư phải có dự án đầu tư...     │
│   [Xem thêm]                                │
├─────────────────────────────────────────────┤
│  📚 Parent Document:                        │
│  Luật Đầu tư 2020 - Full text...            │
├─────────────────────────────────────────────┤
│  🔄 Amendments (nếu có):                    │
│  - Luật sửa đổi 2024...                     │
├─────────────────────────────────────────────┤
│  📖 Citing Articles (nếu có):               │
│  - Nghị định 123/2021/NĐ-CP...              │
└─────────────────────────────────────────────┘
```

### 4.3 References Section

Cuối trang review, bạn sẽ thấy **References**:

- ✅ List tất cả unique citations
- ✅ Mỗi reference có: Article ID, Law ID, Title, Quote
- ✅ Click vào → Mở citation panel

---

## 5. Test Neo4j Graph

### 5.1 Kiểm Tra Neo4j Browser

Open: **http://localhost:7474**

Login:
- Username: `neo4j`
- Password: `password` (hoặc password bạn đã set)

### 5.2 Run Cypher Queries

#### Query 1: Check Documents
```cypher
MATCH (d:Document)
RETURN d.doc_type as type, count(d) as count
ORDER BY count DESC
```

**Expected:** Shows document types but may be empty if not synced yet

#### Query 2: Check Relationships
```cypher
MATCH ()-[r]->()
RETURN type(r) as relationship, count(r) as count
```

**Expected:** 
- Nếu chưa sync documents → Empty (normal)
- Nếu đã sync → Shows relationships

#### Query 3: Visualize Graph
```cypher
MATCH (d:Document)-[r]-(related:Document)
RETURN d, r, related
LIMIT 25
```

### 5.3 Test Citation Context API

```bash
# Get a document ID from PostgreSQL
curl -s http://localhost:8000/api/v1/citations/7ee5540b-008e-431d-8efa-f487880034d4 | python3 -m json.tool

# Expected response:
{
  "node_id": "7ee5540b-...",
  "hierarchy": {},
  "parent": null,
  "amendments": [],
  "citing_articles": [],
  "related_documents": [],
  "context_documents": [],
  "graph_available": true  ← ✅ Neo4j is connected!
}
```

**Note:** Neo4j graph sẽ empty nếu bạn chưa sync documents từ PostgreSQL → Neo4j. Đây là **bình thường**.

### 5.4 (Optional) Sync Documents to Neo4j

Nếu muốn test Neo4j với data:

```bash
# Chạy script sync
cd "/Users/AI/Vinuni/build project qoder"
uv run python database/sync_neo4j.py
```

**Warning:** Script này sẽ sync ~2000 documents, có thể mất 10-20 phút.

Sau khi sync, chạy lại Query 3 ở trên để visualize graph.

---

## 6. Test Chat Legal

### 6.1 Open Chat Page

Open: **http://localhost:3000/chat**

### 6.2 Test Queries

#### Query 1: Investment Procedures
```
Thủ tục đầu tư dự án khu đô thị mới cần những gì?
```

**Expected:**
- ✅ Answer citing Luật Đầu tư 2020
- ✅ 2-3 citations với Luật Đầu tư
- ✅ Confidence: ~80-90%

#### Query 2: Land Transfer
```
Điều kiện chuyển nhượng quyền sử dụng đất theo Luật Đất đai 2024?
```

**Expected:**
- ✅ Answer citing Luật Đất đai 2024
- ✅ Lists conditions from law
- ✅ Citations panel mở ra được

#### Query 3: Tax Obligations
```
Thuế thu nhập doanh nghiệp mới nhất 2024 có gì thay đổi?
```

**Expected:**
- ✅ Answer citing Luật Thuế TNDN 2024
- ✅ Highlights changes
- ✅ Shows relevant articles

#### Query 4: Company Establishment
```
Thành lập công ty TNHH cần hồ sơ gì?
```

**Expected:**
- ✅ Answer citing Luật Doanh nghiệp 2020
- ✅ Lists required documents
- ✅ Mentions procedures

### 6.3 Test Streaming Chat

Chat page nên có streaming (nếu implemented):

```
User: Thủ tục đầu tư?
Bot: [typing...]
     Theo Luật Đầu tư 2020, thủ tục bao gồm: [1]
     1. Đăng ký đầu tư...
     2. Thẩm tra hồ sơ...
     3. Cấp giấy chứng nhận...
```

---

## 7. Kiểm Tra Kết Quả

### 7.1 Performance Metrics

Trong review result, check:

```json
{
  "total_latency_ms": 15000,  // ~15s cho 13 clauses
  "findings": [
    {
      "latency_ms": 1200  // ~1.2s per clause
    }
  ]
}
```

**Expected:**
- ⚡ < 2s per clause (p95)
- ⚡ < 30s total cho 13 clauses

### 7.2 Citation Quality

Check các citations:

| Criteria | Expected | Status |
|----------|----------|--------|
| Relevant documents | Citations match clause topic | ✅ |
| Quote accuracy | Quote matches actual law text | ✅ |
| Document titles | Clear, readable titles | ✅ |
| Law IDs | Correct format (XX/YYYY/QH14) | ✅ |
| Full text access | "Xem thêm" loads complete text | ✅ |

### 7.3 Verification Levels

Expected distribution:

| Level | Count | Description |
|-------|-------|-------------|
| `entailed` | 5-7 | Fully compliant clauses |
| `partially_supported` | 3-4 | Partially compliant |
| `contradicted` | 2-3 | Non-compliant/violations |
| `no_reference` | 0-2 | No matching law found |

### 7.4 Risk Levels

Expected distribution:

| Risk | Count | Color |
|------|-------|-------|
| High | 2-3 | 🔴 Red |
| Medium | 3-4 | 🟡 Yellow |
| Low | 4-5 | 🟢 Green |
| None | 2-3 | ⚪ Gray |

---

## 🐛 Troubleshooting

### Issue 1: Backend không start

```bash
# Check logs
uv run uvicorn apps.review_api.main:app --reload --host 0.0.0.0 --port 8000

# Common errors:
# - "neo4j package not installed" → uv add neo4j
# - "Connection refused" → Check Docker is running
# - "Database does not exist" → Run database/init_db.py
```

### Issue 2: Frontend không connect backend

```bash
# Check .env.local
cd apps/web-app
cat .env.local

# Should have:
NEXT_PUBLIC_API_URL=http://localhost:8000

# If missing, add it and restart frontend
```

### Issue 3: Citations trả về empty

```bash
# Check if documents exist
uv run python -c "
import asyncio, asyncpg
async def check():
    pool = await asyncpg.create_pool('postgresql://postgres:postgres@localhost:5432/legal_review')
    async with pool.acquire() as conn:
        count = await conn.fetchval('SELECT COUNT(*) FROM legal_documents')
        print(f'Documents: {count}')
    await pool.close()
asyncio.run(check())
"

# If count = 0, run ingestion
```

### Issue 4: Neo4j warnings

```
WARNING: UnknownPropertyKeyWarning: title
```

**This is NORMAL** - Neo4j database is empty. Warnings disappear after data sync.

---

## ✅ Checklist Hoàn Thành

- [ ] Backend chạy trên port 8000
- [ ] Frontend chạy trên port 3000
- [ ] Health check trả về "ok"
- [ ] Upload test contract thành công
- [ ] Review hoàn tất với 13 findings
- [ ] Citations hiển thị đúng
- [ ] "Xem thêm" button hoạt động
- [ ] Citation panel mở được
- [ ] References section có dữ liệu
- [ ] Chat legal trả lời được
- [ ] Neo4j connection OK (graph_available: true)
- [ ] Performance < 2s per clause

---

## 📸 Screenshots Cần Capture

1. **Review Results Page** - Full screenshot
2. **Expanded Finding** - Show citations
3. **Citation Panel** - With "Xem thêm" expanded
4. **References Section** - Bottom of page
5. **Chat Response** - With citations
6. **Neo4j Browser** - Graph visualization (nếu có data)

---

## 🎯 Test Cases Coverage

Test contract covers these legal domains from your 50+ ingested documents:

| Legal Domain | Điều Khoản | Expected Citation |
|--------------|------------|-------------------|
| Investment Law | 1.1a | Luật Đầu tư 61/2020 |
| Enterprise Law | 1.1d | Luật Doanh nghiệp 59/2020 |
| Land Law | 1.1c, 6 | Luật Đất đai 31/2024 |
| Tax Law | 1.1e, 3.3, 6.3 | Luật Thuế TNDN 14/2024 |
| Civil Code | Preamble | Bộ luật Dân sự 91/2015 |
| Contract Termination | 9 | Various decrees |
| Force Majeure | 10 | Civil Code provisions |
| Dispute Resolution | 11 | Civil Procedure Law |

**Total: 8 legal domains tested across 13 clauses**

---

## 🚀 Next Steps

Sau khi test xong:

1. **Sync to Neo4j** để test graph features
2. **Add more relationships** để test citation context
3. **Run benchmark** để measure performance
4. **Test with real contracts** từ dataset
5. **Deploy to staging** environment

---

**Happy Testing! 🎉**
