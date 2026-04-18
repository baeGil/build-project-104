# 📋 Expected Output & Context - Comprehensive Test Contract

## 🎯 Contract: HD-2024-TEST-001 (Legal Services & Investment Consulting)

---

## 📊 Overall Expected Results

### **Summary Statistics:**
```
Total clauses: 13
Expected findings: 10-13 (some clauses may not trigger findings)
Expected risk levels:
  - 🔴 High Risk: 2-3 findings
  - 🟡 Medium Risk: 4-5 findings
  - 🟢 Low Risk: 3-4 findings
  - ℹ️ Informational: 1-2 findings

Expected legal domains covered:
  - Luật Đầu tư 61/2020/QH14
  - Luật Doanh nghiệp 59/2020/QH14
  - Luật Đất đai 31/2024/QH15
  - Luật Thuế TNDN 14/2024/QH15
  - Bộ luật Dân sự 91/2015/QH13
```

---

## 🔍 Detailed Expected Output by Clause

### **ĐIỀU 1: PHẠM VI CÔNG VIỆC**

#### Expected Finding 1:
```json
{
  "risk_level": "medium",
  "clause_text": "1.1 Bên A đồng ý cung cấp cho Bên B các dịch vụ tư vấn pháp lý sau...",
  "rationale": "Phạm vi công việc quá rộng, bao gồm 5 lĩnh vực khác nhau (đầu tư, đất đai, doanh nghiệp, thuế). Nên phân chia thành các hợp đồng riêng hoặc có phụ lục chi tiết cho từng lĩnh vực để tránh tranh chấp về sau.",
  "verification": "evidence",
  "confidence": 0.75,
  "revision_suggestion": "Nên tách thành các phụ lục riêng cho từng loại dịch vụ: Phụ lục 1 - Tư vấn đầu tư, Phụ lục 2 - Tư vấn đất đai, v.v. Mỗi phụ lục mô tả chi tiết phạm vi, tiến độ và kết quả mong đợi.",
  "negotiation_note": "Bên B có thể yêu cầu Bên A chỉ tập trung vào 2-3 lĩnh vực trọng tâm để đảm bảo chất lượng tư vấn.",
  "expected_citations": [
    {
      "law_id": "59/2020/QH14",
      "law_title": "Luật Doanh nghiệp 2020",
      "article_id": "Article 4 or related",
      "topic": "Scope of business services"
    },
    {
      "law_id": "61/2020/QH14",
      "law_title": "Luật Đầu tư 2020",
      "article_id": "Article 4 or related",
      "topic": "Investment consulting scope"
    }
  ],
  "inline_citation_map": {
    "1": {"doc_id": "uuid-luat-doanh-nghiep", "title": "Luật Doanh nghiệp 59/2020/QH14"},
    "2": {"doc_id": "uuid-luat-dau-tu", "title": "Luật Đầu tư 61/2020/QH14"}
  }
}
```

#### Expected Finding 2:
```json
{
  "risk_level": "low",
  "clause_text": "1.2 Bên B có nghĩa vụ: a) Cung cấp đầy đủ hồ sơ...",
  "rationale": "Nghĩa vụ của Bên B được quy định rõ ràng nhưng thiếu cơ chế xử lý khi Bên B không cung cấp đầy đủ hồ sơ. Nên bổ sung hậu quả pháp lý nếu vi phạm.",
  "verification": "reasoning",
  "confidence": 0.70,
  "revision_suggestion": "Bổ sung: 'Trường hợp Bên B không cung cấp hồ sơ trong thời hạn 15 ngày, Bên A có quyền tạm dừng thực hiện công việc và không chịu trách nhiệm về tiến độ.'",
  "negotiation_note": "Bên B nên yêu cầu bổ sung danh mục cụ thể hồ sơ cần cung cấp tại Phụ lục 01."
}
```

---

### **ĐIỀU 2: THỜI HẠN THỰC HIỆN**

#### Expected Finding 3:
```json
{
  "risk_level": "medium",
  "clause_text": "2.1 Thời hạn thực hiện: 12 tháng kể từ ngày ký hợp đồng",
  "rationale": "Thời hạn 12 tháng có thể không đủ cho toàn bộ phạm vi công việc, đặc biệt là các thủ tục pháp lý phức tạp liên quan đến đầu tư và đất đai. Thiếu điều khoản xử lý khi chậm tiến độ do nguyên nhân khách quan.",
  "verification": "evidence",
  "confidence": 0.80,
  "revision_suggestion": "Bổ sung: 'Thời hạn có thể được gia hạn bằng văn bản nếu có sự kiện bất khả kháng hoặc thay đổi chính sách pháp luật. Bên A phải thông báo trước 30 ngày nếu dự kiến chậm tiến độ.'",
  "negotiation_note": "Bên B nên đàm phán thêm điều khoản phạt chậm tiến độ: 0.5% giá trị hợp đồng cho mỗi tuần chậm trễ (tối đa 10%).",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 357 or related",
      "topic": "Performance deadlines and breach"
    }
  ]
}
```

---

### **ĐIỀU 3: PHÍ DỊCH VỤ VÀ THANH TOÁN**

#### Expected Finding 4:
```json
{
  "risk_level": "low",
  "clause_text": "3.1 Tổng phí dịch vụ: 500.000.000 VNĐ... 3.2 Phương thức thanh toán...",
  "rationale": "Phí dịch vụ được chia thành 4 đợt thanh toán hợp lý theo tiến độ công việc. Tuy nhiên, thiếu điều khoản xử lý khi Bên B thanh toán chậm và không quy định rõ phí đã bao gồm chi phí phát sinh hay chưa.",
  "verification": "reasoning",
  "confidence": 0.85,
  "revision_suggestion": "Bổ sung: (1) Lãi suất chậm thanh toán: 10%/năm trên số tiền chậm trả; (2) Quy định rõ phí chưa bao gồm chi phí đi lại, công chứng, lệ phí nhà nước; (3) Cơ chế xử lý khi phát sinh công việc ngoài phạm vi.",
  "negotiation_note": "Bên B có thể đàm phán giảm đợt 1 xuống 20% và tăng đợt 4 lên 30% để tạo động lực cho Bên A hoàn thành tốt."
}
```

#### Expected Finding 5:
```json
{
  "risk_level": "high",
  "clause_text": "3.3 Phí chưa bao gồm thuế GTGT 10% theo quy định của Luật Thuế GTGT",
  "rationale": "Viện dẫn 'Luật Thuế GTGT' không chính xác - nên là 'Luật Thuế giá trị gia tăng số 13/2008/QH12 được sửa đổi, bổ sung'. Ngoài ra, thuế GTGT cho dịch vụ tư vấn pháp lý có thể áp dụng mức 10% hoặc 8% tùy thời điểm. Cần kiểm tra văn bản pháp luật hiện hành.",
  "verification": "evidence",
  "confidence": 0.90,
  "revision_suggestion": "Sửa thành: 'Phí chưa bao gồm thuế GTGT theo quy định hiện hành của pháp luật về thuế giá trị gia tăng. Thuế suất áp dụng theo văn bản hướng dẫn của Bộ Tài chính tại thời điểm xuất hóa đơn.'",
  "expected_citations": [
    {
      "law_id": "14/2024/QH15",
      "law_title": "Luật Thuế thu nhập doanh nghiệp 2024",
      "article_id": "Article related to VAT",
      "topic": "Tax obligations"
    }
  ],
  "negotiation_note": "Bên B nên yêu cầu Bên A chịu trách nhiệm về tính chính xác của thuế suất và cung cấp hóa đơn VAT hợp lệ."
}
```

---

### **ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN A**

#### Expected Finding 6:
```json
{
  "risk_level": "medium",
  "clause_text": "4.1 c) Đơn phương chấm dứt hợp đồng nếu Bên B vi phạm nghiêm trọng nghĩa vụ thanh toán",
  "rationale": "Điều khoản cho phép Bên A đơn phương chấm dứt hợp đồng nhưng không quy định rõ 'vi phạm nghiêm trọng' là như thế nào. Theo Bộ luật Dân sự, cần xác định cụ thể mức độ vi phạm (chậm thanh toán bao nhiêu ngày, số tiền bao nhiêu).",
  "verification": "evidence",
  "confidence": 0.85,
  "revision_suggestion": "Sửa thành: 'Đơn phương chấm dứt hợp đồng nếu Bên B chậm thanh toán quá 60 ngày kể từ ngày đến hạn và đã có văn bản nhắc nhở nhưng không khắc phục trong 15 ngày.'",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 420 or related",
      "topic": "Unilateral termination conditions"
    }
  ],
  "negotiation_note": "Bên B nên yêu cầu bổ sung nghĩa vụ của Bên A phải thông báo bằng văn bản trước khi chấm dứt hợp đồng ít nhất 30 ngày."
}
```

#### Expected Finding 7:
```json
{
  "risk_level": "low",
  "clause_text": "4.2 e) Bồi thường thiệt hại trực tiếp do lỗi của Bên A gây ra",
  "rationale": "Bên A chỉ cam kết bồi thường 'thiệt hại trực tiếp' nhưng không giới hạn mức bồi thường. Điều này có thể gây tranh cãi về phạm vi 'trực tiếp'. Nên quy định cụ thể mức giới hạn bồi thường.",
  "verification": "reasoning",
  "confidence": 0.75,
  "revision_suggestion": "Sửa thành: 'Bồi thường thiệt hại trực tiếp do lỗi của Bên A gây ra, với mức giới hạn tối đa bằng 30% giá trị hợp đồng hoặc giá trị phần công việc bị lỗi, tùy theo giá trị nào thấp hơn.'",
  "negotiation_note": "Đây là điều khoản có lợi cho Bên B, có thể giữ nguyên hoặc đàm phán tăng giới hạn bồi thường lên 50%."
}
```

---

### **ĐIỀU 5: QUYỀN VÀ NGHĨA VỤ CỦA BÊN B**

#### Expected Finding 8:
```json
{
  "risk_level": "informational",
  "clause_text": "5.1 Quyền của Bên B... 5.2 Nghĩa vụ của Bên B...",
  "rationale": "Điều khoản cân đối, quy định rõ quyền và nghĩa vụ của Bên B. Tuy nhiên, mục 5.2 d) 'Không tiết lộ thông tin về dịch vụ' quá rộng - có thể hiểu là không được chia sẻ kinh nghiệm làm việc với Bên A cho người khác.",
  "verification": "reasoning",
  "confidence": 0.70,
  "revision_suggestion": "Sửa 5.2 d) thành: 'Không tiết lộ thông tin mật, bí mật kinh doanh của Bên A nhận được trong quá trình thực hiện hợp đồng, trừ thông tin đã công khai.'",
  "negotiation_note": "Điều khoản này đã khá cân bằng, không cần đàm phán nhiều."
}
```

---

### **ĐIỀU 6: CHUYỂN NHƯỢNG QUYỀN SỬ DỤNG ĐẤT**

#### Expected Finding 9: ⚠️ HIGH PRIORITY
```json
{
  "risk_level": "high",
  "clause_text": "6.1 Bên B có nghĩa vụ đảm bảo dự án đáp ứng các điều kiện chuyển nhượng theo Luật Đất đai 2024...",
  "rationale": "Điều khoản này đặt toàn bộ nghĩa vụ đảm bảo điều kiện chuyển nhượng lên Bên B, nhưng đây là hợp đồng DỊCH VỤ TƯ VẤN, không phải hợp đồng CHUYỂN NHƯỢNG. Bên A là bên tư vấn, không phải bên chuyển nhượng đất. Điều này có thể tạo rủi ro pháp lý nếu dự án không đáp ứng điều kiện chuyển nhượng.",
  "verification": "evidence",
  "confidence": 0.95,
  "revision_suggestion": "Sửa thành: 'Bên A có nghĩa vụ tư vấn cho Bên B về các điều kiện chuyển nhượng quyền sử dụng đất theo Luật Đất đai 2024. Bên B chịu trách nhiệm cuối cùng trong việc đảm bảo dự án đáp ứng các điều kiện này. Bên A không bảo đảm kết quả chuyển nhượng thành công.'",
  "expected_citations": [
    {
      "law_id": "31/2024/QH15",
      "law_title": "Luật Đất đai 2024",
      "article_id": "Article 188 or related",
      "topic": "Conditions for land use right transfer"
    }
  ],
  "negotiation_note": "🔴 Đây là điều khoản QUAN TRỌNG NHẤT cần sửa đổi. Bên B phải hiểu rõ đây là hợp đồng tư vấn, không phải hợp đồng chuyển nhượng. Bên A chỉ có nghĩa vụ tư vấn, không bảo đảm kết quả."
}
```

#### Expected Finding 10:
```json
{
  "risk_level": "high",
  "clause_text": "6.3 Thuế thu nhập cá nhân từ chuyển nhượng BĐS: 2% trên giá chuyển nhượng theo Luật Thuế TNDN",
  "rationale": "Sai sót pháp lý nghiêm trọng: (1) Thuế TNCN từ chuyển nhượng BĐS là 2% theo Luật Thuế TNCN (không phải Luật Thuế TNDN); (2) Đây là hợp đồng dịch vụ tư vấn, không phải hợp đồng chuyển nhượng BĐS nên điều khoản này không phù hợp; (3) Nếu Bên B là công ty (không phải cá nhân), sẽ áp dụng thuế TNDN chứ không phải thuế TNCN.",
  "verification": "evidence",
  "confidence": 0.98,
  "revision_suggestion": "XÓA điều khoản này khỏi hợp đồng dịch vụ tư vấn. Nếu cần, đưa vào Phụ lục tư vấn riêng về thuế với nội dung: 'Bên A sẽ tư vấn về nghĩa vụ thuế theo Luật Thuế TNCN và Luật Thuế TNDN áp dụng cho giao dịch chuyển nhượng BĐS.'",
  "expected_citations": [
    {
      "law_id": "14/2024/QH15",
      "law_title": "Luật Thuế thu nhập doanh nghiệp 2024",
      "article_id": "Article related to corporate tax",
      "topic": "Corporate income tax vs personal income tax"
    },
    {
      "law_id": "31/2024/QH15",
      "law_title": "Luật Đất đai 2024",
      "article_id": "Article related to transfer taxes",
      "topic": "Tax obligations for land transfer"
    }
  ],
  "negotiation_note": "🔴 PHẢI XÓA hoặc SỬA LẠI hoàn toàn. Đây là hợp đồng tư vấn, không phải hợp đồng chuyển nhượng."
}
```

---

### **ĐIỀU 7: BẢO MẬT THÔNG TIN**

#### Expected Finding 11:
```json
{
  "risk_level": "low",
  "clause_text": "7.1 Các bên cam kết bảo mật tuyệt đối thông tin... 7.2 Thời hạn bảo mật: 05 năm...",
  "rationale": "Điều khoản bảo mật khá đầy đủ với thời hạn 5 năm là hợp lý. Tuy nhiên, thiếu quy định về biện pháp bảo mật cụ thể (mã hóa, lưu trữ, truy cập) và chế tài xử lý vi phạm bảo mật.",
  "verification": "reasoning",
  "confidence": 0.80,
  "revision_suggestion": "Bổ sung: (1) Biện pháp bảo mật: mã hóa dữ liệu, giới hạn người truy cập, lưu trữ an toàn; (2) Chế tài: Phạt vi phạm 50 triệu VNĐ cho mỗi lần tiết lộ thông tin mật; (3) Nghĩa vụ tiêu hủy tài liệu mật sau khi chấm dứt hợp đồng.",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 34 or related",
      "topic": "Confidentiality obligations"
    }
  ],
  "negotiation_note": "Bên B có thể yêu cầu tăng thời hạn bảo mật lên 10 năm đối với thông tin đặc biệt nhạy cảm."
}
```

---

### **ĐIỀU 8: TRÁCH NHIỆM BỒI THƯỜNG THIỆT HẠI**

#### Expected Finding 12:
```json
{
  "risk_level": "medium",
  "clause_text": "8.2 Mức bồi thường không vượt quá 30% giá trị hợp đồng",
  "rationale": "Giới hạn bồi thường 30% là hợp lý theo thông lệ thương mại. Tuy nhiên, Điều 4.2 e) cũng đề cập bồi thường nhưng không giới hạn mức. Có sự không nhất quán giữa hai điều khoản này.",
  "verification": "evidence",
  "confidence": 0.85,
  "revision_suggestion": "Thêm tham chiếu chéo: 'Mức bồi thường theo Điều 4.2 e) cũng áp dụng giới hạn tối đa 30% giá trị hợp đồng như quy định tại Điều 8.2.'",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 359 or related",
      "topic": "Damage compensation limits"
    }
  ],
  "negotiation_note": "Bên B có thể đàm phán tăng giới hạn lên 50% đối với vi phạm nghiêm trọng (sai sót pháp lý gây thiệt hại lớn)."
}
```

---

### **ĐIỀU 9: CHẤM DỨT HỢP ĐỒNG**

#### Expected Finding 13:
```json
{
  "risk_level": "medium",
  "clause_text": "9.2 a) Bên có quyền đơn phương chấm dứt phải báo trước 30 ngày bằng văn bản",
  "rationale": "Thời gian báo trước 30 ngày là hợp lý. Tuy nhiên, mục 9.2 b) 'chậm thanh toán quá 60 ngày' mâu thuẫn với yêu cầu báo trước 30 ngày - không rõ có cần báo trước không khi đã chậm 60 ngày.",
  "verification": "reasoning",
  "confidence": 0.80,
  "revision_suggestion": "Làm rõ: 'Trường hợp Bên B chậm thanh toán quá 60 ngày, Bên A có quyền đơn phương chấm dứt hợp đồng sau khi đã gửi văn bản nhắc nhở và Bên B không khắc phục trong 15 ngày kể từ ngày nhận được nhắc nhở.'",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 420 or related",
      "topic": "Unilateral termination notice period"
    }
  ],
  "negotiation_note": "Bên B nên yêu cầu thêm nghĩa vụ hòa giải trước khi đơn phương chấm dứt hợp đồng."
}
```

#### Expected Finding 14:
```json
{
  "risk_level": "low",
  "clause_text": "9.2 d) Bên bị tuyên bố phá sản hoặc giải thể",
  "rationale": "Sử dụng từ '宣告' (tiếng Trung) thay vì 'tuyên bố' (tiếng Việt) - lỗi chính tả/ngôn ngữ nghiêm trọng trong văn bản pháp lý tiếng Việt.",
  "verification": "evidence",
  "confidence": 0.99,
  "revision_suggestion": "Sửa 'bị宣告 phá sản' thành 'bị Tòa án tuyên bố phá sản hoặc quyết định giải thể theo quy định pháp luật.'",
  "negotiation_note": "Lỗi này cần sửa ngay trước khi ký kết."
}
```

---

### **ĐIỀU 10: BẤT KHẢ KHÁNG**

#### Expected Finding 15:
```json
{
  "risk_level": "low",
  "clause_text": "10.1 Sự kiện bất khả kháng bao gồm: thiên tai, hỏa hoạn, chiến tranh, dịch bệnh, thay đổi chính sách pháp luật",
  "rationale": "Danh mục sự kiện bất khả kháng khá đầy đủ. Tuy nhiên, 'thay đổi chính sách pháp luật' có thể gây tranh cãi - không phải mọi thay đổi đều là bất khả kháng. Nên bổ sung tiêu chí: 'thay đổi làm cho việc thực hiện hợp đồng trở nên bất hợp pháp hoặc bất khả thi.'",
  "verification": "reasoning",
  "confidence": 0.75,
  "revision_suggestion": "Sửa thành: 'Sự kiện bất khả kháng bao gồm: thiên tai, hỏa hoạn, chiến tranh, dịch bệnh trên diện rộng, và thay đổi chính sách pháp luật làm cho việc thực hiện hợp đồng trở nên bất hợp pháp hoặc bất khả thi về mặt kinh tế (chi phí tăng trên 50%).'",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article 156 or related",
      "topic": "Force majeure definition"
    }
  ],
  "negotiation_note": "Điều khoản này khá công bằng, có thể giữ nguyên hoặc bổ sung tiêu chí cụ thể."
}
```

---

### **ĐIỀU 11: GIẢI QUYẾT TRANH CHẤP**

#### Expected Finding 16:
```json
{
  "risk_level": "low",
  "clause_text": "11.2 Nếu không thương lượng được trong 30 ngày, tranh chấp sẽ được giải quyết tại Tòa án nhân dân TP. Đà Nẵng",
  "rationale": "Lựa chọn Tòa án TP. Đà Nẵng là hợp lý vì Bên B đặt trụ sở tại đây. Tuy nhiên, nên bổ sung cơ chế hòa giải thương mại trước khi kiện ra Tòa án để tiết kiệm thời gian và chi phí.",
  "verification": "reasoning",
  "confidence": 0.70,
  "revision_suggestion": "Thêm: 'Trước khi khởi kiện ra Tòa án, các bên có nghĩa vụ tham gia hòa giải thương mại tại Trung tâm Hòa giải thuộc VCCI hoặc tổ chức hòa giải được cả hai bên chấp thuận. Thời hạn hòa giải không quá 30 ngày.'",
  "expected_citations": [
    {
      "law_id": "91/2015/QH13",
      "law_title": "Bộ luật Dân sự 2015",
      "article_id": "Article related to dispute resolution",
      "topic": "Dispute resolution mechanisms"
    }
  ],
  "negotiation_note": "Bên A có thể yêu cầu chọn Tòa án TP. HCM nếu muốn thuận tiện cho mình. Đây là điểm cần đàm phán."
}
```

---

### **ĐIỀU 12: ĐIỀU KHOẢN CHUNG**

#### Expected Finding 17:
```json
{
  "risk_level": "informational",
  "clause_text": "12.1-12.5 Các điều khoản chung...",
  "rationale": "Các điều khoản chung khá đầy đủ và chuẩn mực. Điều 12.5 về thay đổi pháp luật là quan trọng và phù hợp với tính chất hợp đồng tư vấn pháp lý dài hạn.",
  "verification": "reasoning",
  "confidence": 0.90,
  "revision_suggestion": "Không cần sửa đổi lớn. Có thể bổ sung: 'Hợp đồng này được điều chỉnh bởi pháp luật Việt Nam.' để rõ ràng về luật áp dụng.",
  "negotiation_note": "Điều khoản này đã tốt, không cần đàm phán nhiều."
}
```

---

## 📈 Quality Metrics to Check

### **1. Citation Accuracy** ✅
```
Expected: Each finding should have 1-3 valid citations
Check:
  ✅ Citations reference correct laws (Luật Đầu tư, Luật Đất đai, etc.)
  ✅ Article IDs are plausible (not random numbers)
  ✅ Topics match the finding content
  ✅ Document titles are in Vietnamese
```

### **2. Risk Level Distribution** ✅
```
Expected:
  🔴 High Risk: 2-3 findings (Điều 6, Điều 9.2d)
  🟡 Medium Risk: 4-5 findings (Điều 1, 2, 4, 8, 9)
  🟢 Low Risk: 3-4 findings (Điều 3, 5, 7, 10, 11)
  ℹ️ Informational: 1-2 findings (Điều 5, 12)

Red flags:
  ❌ All findings are same risk level
  ❌ No high risk findings for obvious issues
  ❌ Too many high risk findings (>50%)
```

### **3. Confidence Scores** ✅
```
Expected range: 0.65 - 0.95
Average: ~0.80

Good signs:
  ✅ High confidence (0.85+) for clear legal errors (Điều 6.3, 9.2d)
  ✅ Medium confidence (0.70-0.85) for recommendations
  ✅ Varies by finding (not all same score)

Red flags:
  ❌ All scores are exactly the same (e.g., all 0.80)
  ❌ Scores too low (<0.60) - model uncertain
  ❌ Scores too high (>0.95) for everything - overconfident
```

### **4. Vietnamese Language Quality** ✅
```
Check:
  ✅ All output in proper Vietnamese
  ✅ Legal terminology accurate
  ✅ Grammar and spelling correct
  ✅ Professional tone

Red flags:
  ❌ Mixed English/Vietnamese
  ❌ Awkward phrasing
  ❌ Incorrect legal terms
  ❌ Spelling errors (except finding 14 which tests the Chinese character bug)
```

### **5. Revision Suggestions** ✅
```
Expected:
  ✅ Each finding has specific, actionable suggestion
  ✅ Suggestions reference specific clause numbers
  ✅ Suggestions are legally sound
  ✅ Suggestions include sample text

Red flags:
  ❌ Generic suggestions ("Nên tham khảo luật sư")
  ❌ No suggestions provided
  ❌ Suggestions contradict Vietnamese law
  ❌ Suggestions too vague to implement
```

### **6. Negotiation Notes** ✅
```
Expected:
  ✅ Notes provide strategic advice
  ✅ Notes identify negotiable vs non-negotiable terms
  ✅ Notes consider both parties' perspectives
  ✅ Notes prioritize critical issues

Red flags:
  ❌ No negotiation notes
  ❌ Notes are identical for all findings
  ❌ Notes favor only one party
  ❌ Notes suggest illegal strategies
```

---

## 🎯 Critical Test Cases

### **Test Case 1: Legal Error Detection** 🔴
```
Clause: 6.3 (Tax reference error)
Expected: HIGH RISK finding with correct tax law citation
Pass criteria:
  ✅ Risk level = "high"
  ✅ Mentions wrong law reference (Luật Thuế TNDN vs TNCN)
  ✅ Suggests correct law
  ✅ Confidence >= 0.90
```

### **Test Case 2: Language Error Detection** 🔴
```
Clause: 9.2 d) (Chinese character)
Expected: LOW/HIGH RISK finding identifying the error
Pass criteria:
  ✅ Identifies "宣告" as error
  ✅ Suggests "tuyên bố" as correction
  ✅ Confidence >= 0.95
```

### **Test Case 3: Contract Type Confusion** 🔴
```
Clause: 6.1 (Land transfer in consulting contract)
Expected: HIGH RISK finding
Pass criteria:
  ✅ Identifies mismatch between contract type and clause content
  ✅ Explains why it's problematic
  ✅ Suggests rewording or moving to separate agreement
  ✅ Risk level = "high"
```

### **Test Case 4: Cross-Reference Consistency** 🟡
```
Clauses: 4.2 e) and 8.2 (Compensation limits)
Expected: MEDIUM RISK finding
Pass criteria:
  ✅ Identifies inconsistency
  ✅ Explains the conflict
  ✅ Suggests adding cross-reference
  ✅ Verification = "evidence" or "reasoning"
```

### **Test Case 5: Citation Quality** ✅
```
All findings
Expected: Valid citations to Vietnamese legal documents
Pass criteria:
  ✅ At least 80% of findings have citations
  ✅ Citations reference actual laws in database
  ✅ Law IDs match ingested documents (61/2020, 59/2020, 31/2024, 14/2024, 91/2015)
  ✅ Full text loads correctly in CitationPanel
```

---

## 📊 Scoring Rubric

### **Overall Quality Score:**

| Criteria | Weight | Excellent (90-100) | Good (70-89) | Fair (50-69) | Poor (<50) |
|----------|--------|-------------------|--------------|--------------|------------|
| **Legal Accuracy** | 30% | All findings legally sound | Minor errors | Several errors | Major errors |
| **Citation Quality** | 20% | All citations valid & relevant | 80%+ valid | 60-80% valid | <60% valid |
| **Risk Assessment** | 15% | Accurate risk levels | Mostly accurate | Some wrong | Many wrong |
| **Vietnamese Quality** | 15% | Perfect language | Minor issues | Noticeable issues | Poor quality |
| **Actionability** | 10% | All suggestions specific | Most specific | Some vague | Very vague |
| **Completeness** | 10% | All clauses reviewed | 80%+ covered | 60-80% covered | <60% covered |

### **Pass/Fail Criteria:**

```
✅ PASS: Overall score >= 75 AND no critical test cases failed
⚠️ NEEDS IMPROVEMENT: Overall score 60-74 OR 1 critical test case failed
❌ FAIL: Overall score < 60 OR 2+ critical test cases failed
```

---

## 🔍 How to Test

### **Step 1: Run Contract Review**
```bash
# Via frontend:
1. Go to http://localhost:3000/review
2. Copy content from comprehensive_test_contract.txt
3. Paste into text area
4. Click "Rà soát Hợp đồng"
5. Wait for results

# Via API:
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d @test-contract.json
```

### **Step 2: Check Output Against Expected**
```
1. Count findings - should be 10-13
2. Check risk level distribution
3. Verify citations load correctly
4. Read each rationale - does it make legal sense?
5. Check revision suggestions - are they actionable?
6. Verify Vietnamese language quality
```

### **Step 3: Run Critical Test Cases**
```
1. Find finding about Điều 6.3 - is it HIGH RISK?
2. Find finding about Điều 9.2d - does it catch Chinese character?
3. Find finding about Điều 6.1 - does it identify contract type issue?
4. Click 3-5 citations - does full text load?
5. Check confidence scores - are they realistic?
```

### **Step 4: Score the Output**
```
Use the scoring rubric above to calculate overall score.
Target: >= 75 for PASS
```

---

## 📝 Notes

1. **This is a reference guide** - actual output may vary slightly
2. **Focus on critical test cases** - these are must-pass
3. **Check citations carefully** - this is core functionality
4. **Vietnamese quality matters** - this is for Vietnamese lawyers
5. **Iterate and improve** - use failures to fix the system

---

**Document Version:** 1.0
**Created:** 2026-04-15
**Author:** AI Assistant
**Purpose:** Quality assurance reference for contract review system testing
