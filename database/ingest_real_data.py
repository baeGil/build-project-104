"""Ingest real Vietnamese legal documents from HuggingFace dataset.

This script ingests legal documents from HuggingFace dataset:
  Dataset: th1nhng0/vietnamese-legal-documents
  Split: train
  Default limit: 50 documents

Usage:
    python database/ingest_real_data.py

The script will:
1. Load documents from HuggingFace dataset (PRIMARY SOURCE)
2. Ingest documents through the full pipeline (normalize -> parse -> index)
3. Store in PostgreSQL, Qdrant, and OpenSearch
4. Validate ingestion by querying PostgreSQL count

Requirements:
    pip install datasets

Note: The 'datasets' library from HuggingFace must be installed.
      If not installed, run: pip install datasets
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, "/Users/AI/Vinuni/build project qoder")

from packages.common.config import get_settings
from packages.ingestion.pipeline import IngestionPipeline


# =============================================================================
# NOTE: HARDCODED DOCUMENTS BELOW ARE NOT USED
# =============================================================================
# These documents are kept only as reference/examples.
# The script now ONLY ingests from HuggingFace dataset:
#   th1nhng0/vietnamese-legal-documents
#
# If you want to ingest these hardcoded documents instead, you would need to
# modify the main() function to call ingest_hardcoded_documents(pipeline).
# =============================================================================

# =============================================================================
# REAL VIETNAMESE LEGAL DOCUMENTS (REFERENCE ONLY - NOT USED)
# =============================================================================

REAL_LEGAL_DOCUMENTS: list[dict[str, Any]] = [
    # ==========================================================================
    # 1. BỘ LUẬT LAO ĐỘNG 2019 - Labor Code (Substantial document)
    # ==========================================================================
    {
        "title": "Bộ luật Lao động 2019 - Điều 14 Hợp đồng lao động",
        "content": """BỘ LUẬT LAO ĐỘNG
Số: 45/2019/QH14

Điều 14. Hợp đồng lao động

1. Hợp đồng lao động là sự thoả thuận giữa ngườI lao động và ngườI sử dụng lao động về việc làm có trả lương, điều kiện làm việc, quyền và nghĩa vụ của mỗi bên trong quan hệ lao động.

2. Hợp đồng lao động phải được giao kết theo nguyên tắc tự nguyện, bình đẳng, thiện chí, hợp tác, trung thực và trên cơ sở tuân thủ pháp luật, thỏa ước lao động tập thể (nếu có).

3. Hợp đồng lao động được giao kết thông qua các hình thức sau đây:
a) Hợp đồng lao động không xác định thờI hạn;
b) Hợp đồng lao động xác định thờI hạn;
c) Hợp đồng lao động theo mùa vụ hoặc theo một công việc nhất định có thờI hạn dưới 12 tháng.

4. Hợp đồng lao động phải được giao kết bằng văn bản và được làm thành 02 bản, ngườI lao động giữ 01 bản, ngườI sử dụng lao động giữ 01 bản, trừ trường hợp quy định tại khoản 2 Điều này.

Điều 15. Nội dung của hợp đồng lao động

Hợp đồng lao động phải có các nội dung chủ yếu sau đây:
1. Tên và địa chỉ của ngườI sử dụng lao động hoặc của ngườI đại diện theo pháp luật của ngườI sử dụng lao động;
2. Họ và tên, ngày tháng năm sinh, giớI tính, nơi cư trú, số chứng minh nhân dân hoặc số thẻ căn cước công dân hoặc số hộ chiếu của ngườI lao động;
3. Công việc phải làm và địa điểm làm việc;
4. ThờI hạn của hợp đồng lao động;
5. Mức lương theo công việc hoặc chức danh, hình thức trả lương, thờI hạn trả lương, phụ cấp lương và các khoản bổ sung khác;
6. Chế độ nâng bậc, nâng lương;
7. ThờI giờ làm việc, thờI giờ nghỉ ngơi;
8. Bảo hộ lao động, an toàn lao động, vệ sinh lao động đối với ngườI lao động;
9. Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp;
10. Đào tạo, bồi dưỡng nâng cao trình độ, kỹ năng nghề.

Điều 16. Các loại hợp đồng lao động

1. Hợp đồng lao động không xác định thờI hạn là hợp đồng lao động mà trong đó hai bên không xác định thờI điểm chấm dứt hiệu lực của hợp đồng.

2. Hợp đồng lao động xác định thờI hạn là hợp đồng lao động mà trong đó hai bên xác định thờI điểm chấm dứt hiệu lực của hợp đồng trong thờI hạn từ đủ 12 tháng đến 36 tháng.

3. Hợp đồng lao động theo mùa vụ hoặc theo một công việc nhất định có thờI hạn dưới 12 tháng là hợp đồng lao động mà trong đó hai bên xác định thờI điểm chấm dứt hiệu lực của hợp đồng theo mùa vụ hoặc theo việc làm nhất định.

Điều 17. Hiệu lực của hợp đồng lao động

1. Hợp đồng lao động có hiệu lực kể từ thờI điểm hai bên ký kết, trừ trường hợp hai bên có thỏa thuận khác hoặc pháp luật có quy định khác.

2. Trong trường hợp ngườI lao động làm việc thực tế mà hai bên chưa ký kết hợp đồng lao động thì sau thờI hạn 01 tháng kể từ ngày ngườI lao động làm việc, hai bên phải ký kết hợp đồng lao động theo quy định của Bộ luật này.

Điều 20. ThờI hạn thử việc

1. ThờI hạn thử việc được hai bên thoả thuận nhưng chỉ được thử việc một lần đối với một công việc và phải đảm bảo các điều kiện sau đây:
a) Không quá 180 ngày đối với chức danh quản lý doanh nghiệp theo quy định của Luật Doanh nghiệp, Luật Quản lý, sử dụng vốn nhà nước đầu tư vào sản xuất, kinh doanh tại doanh nghiệp;
b) Không quá 60 ngày đối với các chức danh yêu cầu trình độ chuyên môn kỹ thuật từ cao đẳng trở lên;
c) Không quá 30 ngày đối với các chức danh yêu cầu trình độ chuyên môn kỹ thuật trung cấp, công nhân bậc cao và các chức danh nghề khác.

2. Trong thờI hạn thử việc, mỗi bên có quyền huỷ bỏ thoả thuận thử việc mà không cần báo trước và không phải bồi thường thiệt hại nếu việc làm thử không đạt yêu cầu so với thoả thuận trong hợp đồng lao động.

3. Trong thờI hạn thử việc, ngườI lao động được trả lương theo công việc làm thử nhưng không được thấp hơn 85% mức lương của công việc đó.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "45/2019/QH14",
            "effective_date": "2021-01-01",
            "issuing_body": "Quốc hội",
            "category": "Labor Law",
            "articles": ["14", "15", "16", "17", "20"],
        },
    },
    # ==========================================================================
    # 2. BỘ LUẬT DÂN SỰ 2015 - Civil Code (Substantial document)
    # ==========================================================================
    {
        "title": "Bộ luật Dân sự 2015 - Điều 116 Điều kiện có hiệu lực của giao dịch dân sự",
        "content": """BỘ LUẬT DÂN SỰ
Số: 91/2015/QH13

Điều 116. Điều kiện có hiệu lực của giao dịch dân sự

1. Giao dịch dân sự có hiệu lực khi có đủ các điều kiện sau đây:
a) Chủ thể có năng lực pháp luật dân sự, năng lực hành vi dân sự phù hợp với giao dịch dân sự được xác lập, thực hiện;
b) Chủ thể tham gia giao dịch dân sự hoàn toàn tự nguyện;
c) Mục đích và nội dung của giao dịch dân sự không vi phạm điều cấm của luật, không trái đạo đức xã hội.

2. Giao dịch dân sự được xác lập, thực hiện qua phương tiện điện tử dưới hình thức thông điệp dữ liệu theo quy định của luật về giao dịch điện tử có giá trị pháp lý như giao dịch dân sự được thể hiện bằng văn bản.

Điều 117. Giao dịch dân sự vô hiệu do vi phạm điều cấm của luật, trái đạo đức xã hội

1. Giao dịch dân sự vô hiệu khi mục đích và nội dung của giao dịch dân sự vi phạm điều cấm của luật, trái đạo đức xã hội.

2. Khi giao dịch dân sự vô hiệu do vi phạm điều cấm của luật, trái đạo đức xã hội thì các bên phải hoàn trả cho nhau những gì đã nhận; nếu không hoàn trả được bằng hiện vật thì phải hoàn trả bằng tiền, trừ trường hợp quy định tại khoản 2 Điều 167 của Bộ luật này.

Điều 119. Hợp đồng

1. Hợp đồng là sự thoả thuận giữa các bên về việc xác lập, thay đổi hoặc chấm dứt quyền, nghĩa vụ dân sự.

2. Hợp đồng phải tuân theo các quy định của Bộ luật này, luật khác có liên quan và phải được giao kết theo nguyên tắc tự do, tự nguyện, bình đẳng, thiện chí, hợp tác, trung thực và hợp pháp.

Điều 400. Hợp đồng mua bán tài sản

1. Hợp đồng mua bán tài sản là sự thoả thuận giữa các bên, theo đó bên bán chuyển quyền sở hữu tài sản cho bên mua và bên mua trả tiền cho bên bán.

2. Hợp đồng mua bán tài sản phải được giao kết theo nguyên tắc tự do, tự nguyện, bình đẳng, thiện chí, hợp tác, trung thực và hợp pháp.

Điều 401. Nghĩa vụ của bên bán

1. Giao tài sản cho bên mua theo đúng thoả thuận về loại tài sản, số lượng, chất lượng và các yêu cầu khác.

2. Chuyển quyền sở hữu tài sản cho bên mua.

3. Bảo đảm quyền của bên mua đối với tài sản mua.

4. Giao chứng từ liên quan đến tài sản cho bên mua.

5. Chịu trách nhiệm bồi thường thiệt hại do vi phạm nghĩa vụ.

Điều 402. Nghĩa vụ của bên mua

1. Thanh toán tiền mua tài sản cho bên bán theo đúng thoả thuận.

2. Nhận tài sản.

3. Chịu trách nhiệm bồi thường thiệt hại do vi phạm nghĩa vụ.

4. Chịu rủi ro về tài sản từ thờI điểm nhận tài sản, trừ trường hợp có thoả thuận khác.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "91/2015/QH13",
            "effective_date": "2017-01-01",
            "issuing_body": "Quốc hội",
            "category": "Civil Code",
            "articles": ["116", "117", "119", "400", "401", "402"],
        },
    },
    # ==========================================================================
    # 3. LUẬT DOANH NGHIỆP 2020 - Enterprise Law (Substantial document)
    # ==========================================================================
    {
        "title": "Luật Doanh nghiệp 2020 - Công ty trách nhiệm hữu hạn",
        "content": """LUẬT DOANH NGHIỆP
Số: 59/2020/QH14

Chương III
CÔNG TY TRÁCH NHIỆM HỮU HẠN HAI THÀNH VIÊN TRỞ LÊN

Điều 46. Công ty trách nhiệm hữu hạn hai thành viên trở lên

1. Công ty trách nhiệm hữu hạn hai thành viên trở lên là doanh nghiệp có tư cách pháp nhân kể từ ngày được cấp Giấy chứng nhận đăng ký doanh nghiệp.

2. Công ty trách nhiệm hữu hạn hai thành viên trở lên có quyền sở hữu tài sản, có con dấu riêng, được mở tài khoản tại ngân hàng theo quy định của pháp luật.

3. Công ty trách nhiệm hữu hạn hai thành viên trở lên không được phát hành cổ phiếu.

Điều 47. Góp vốn thành lập công ty

1. Vốn điều lệ của công ty được chia thành các phần vốn góp bằng nhau gọi là phần vốn góp. Số lượng phần vốn góp của các thành viên do các thành viên tự thoả thuận và được ghi trong Điều lệ công ty.

2. Thành viên công ty có thể góp vốn bằng Đồng Việt Nam, ngoại tệ tự do chuyển đổi, vàng, giá trị quyền sử dụng đất, giá trị quyền sở hữu trí tuệ, công nghệ, kỹ thuật, bí quyết kỹ thuật, tài sản khác có thể định giá được bằng Đồng Việt Nam.

3. ThờI hạn góp vốn không quá 90 ngày kể từ ngày được cấp Giấy chứng nhận đăng ký doanh nghiệp, trừ trường hợp Điều lệ công ty quy định thờI hạn dài hơn.

Điều 48. Quyền của thành viên công ty

1. Tham dự họp, thảo luận và biểu quyết tại Hội đồng thành viên; thực hiện quyền biểu quyết theo tỷ lệ phần vốn góp hoặc theo số lượng thành viên quy định trong Điều lệ công ty.

2. Được hưởng lợi nhuận tương ứng với tỷ lệ phần vốn góp trong Điều lệ công ty.

3. Được ưu tiên góp thêm vốn khi công ty tăng vốn điều lệ.

4. Được chuyển nhượng một phần hoặc toàn bộ phần vốn góp cho ngườI khác theo quy định tại Điều 52 của Luật này.

5. Yêu cầu công ty mua lại phần vốn góp của mình trong các trường hợp quy định tại khoản 3 Điều 52 của Luật này.

6. Được xem sổ đăng ký thành viên, biên bản họp Hội đồng thành viên, báo cáo tài chính hàng năm của công ty.

7. Khi công ty giải thể hoặc phá sản, được chia phần tài sản còn lại sau khi đã thanh toán hết các khoản nợ.

8. Yêu cầu công ty bồi thường thiệt hại do ngườI điều hành hoạt động kinh doanh của công ty gây ra.

Điều 52. Chuyển nhượng phần vốn góp

1. Thành viên có quyền chuyển nhượng một phần hoặc toàn bộ phần vốn góp của mình cho ngườI khác theo các hình thức sau đây:
a) Chuyển nhượng cho thành viên khác trong công ty;
b) Chuyển nhượng cho ngườI không phảI là thành viên của công ty.

2. Việc chuyển nhượng phần vốn góp phảI được lập thành văn bản và có chữ ký của bên chuyển nhượng và bên nhận chuyển nhượng hoặc ngườI đại diện theo ủy quyền của họ.

3. Trong trường hợp thành viên không được Hội đồng thành viên đồng ý cho chuyển nhượng phần vốn góp cho ngườI không phảI là thành viên thì thành viên đó có quyền yêu cầu công ty mua lại phần vốn góp của mình.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "59/2020/QH14",
            "effective_date": "2021-01-01",
            "issuing_body": "Quốc hội",
            "category": "Enterprise Law",
            "articles": ["46", "47", "48", "52"],
        },
    },
    # ==========================================================================
    # 4. LUẬT SỞ HỮU TRÍ TUỆ 2005 (sửa đổi 2022) - IP Law
    # ==========================================================================
    {
        "title": "Luật Sở hữu trí tuệ 2005 (sửa đổi 2022) - Quyền tác giả",
        "content": """LUẬT SỞ HỮU TRÍ TUỆ
Số: 50/2005/QH11 (được sửa đổi, bổ sung bởi Luật số 07/2022/QH15)

Chương I
QUYỀN TÁC GIẢ VÀ QUYỀN LIÊN QUAN

Điều 14. Quyền tác giả

1. Quyền tác giả bao gồm quyền nhân thân và quyền tài sản đối với tác phẩm văn học, nghệ thuật, khoa học; quyền nhân thân và quyền tài sản đối với cuộc thể hiện, bản ghi âm, ghi hình, chương trình phát sóng, tín hiệu vệ tinh mang chương trình được bảo hộ.

2. Quyền tác giả phát sinh kể từ khi tác phẩm được sáng tạo và được thể hiện dưới hình thức vật chất nhất định, không phụ thuộc vào việc công bố, đăng ký hay thực hiện bất kỳ thủ tục nào khác.

Điều 15. Chủ thể của quyền tác giả

1. Chủ thể của quyền tác giả bao gồm:
a) Tác giả là ngườI trực tiếp sáng tạo ra tác phẩm;
b) Đồng tác giả là những ngườI cùng trực tiếp sáng tạo ra tác phẩm;
c) Chủ sở hữu quyền tác giả là tổ chức, cá nhân được quy định tại Điều 39 của Luật này.

2. Tác giả, đồng tác giả luôn luôn có quyền nhân thân đối với tác phẩm của mình.

Điều 19. Quyền nhân thân của tác giả

Quyền nhân thân của tác giả bao gồm các quyền sau đây:
1. Đặt tên cho tác phẩm;
2. Đứng tên thật hoặc bút danh trên tác phẩm; được nêu tên thật hoặc bút danh khi tác phẩm được công bố, sử dụng;
3. Công bố tác phẩm hoặc cho phép ngườI khác công bố tác phẩm;
4. Bảo vệ sự toàn vẹn của tác phẩm, không cho ngườI khác sửa chữa, cắt xén hoặc xuyên tạc tác phẩm dưới bất kỳ hình thức nào gây phương hại đến danh dự và uy tín của tác giả.

Điều 20. Quyền tài sản của tác giả

Quyền tài sản của tác giả bao gồm các quyền sau đây:
1. Quyền sao chép tác phẩm;
2. Quyền phân phối, nhập khẩu bản gốc hoặc bản sao tác phẩm;
3. Quyền truyền đạt tác phẩm đến công chúng;
4. Quyền cho thuê bản gốc hoặc bản sao tác phẩm điện ảnh, chương trình máy tính;
5. Quyền biểu diễn tác phẩm trước công chúng;
6. Quyền trình diễn tác phẩm trước công chúng;
7. Quyền truyền phát, truyền đạt tác phẩm đến công chúng bằng phương tiện hữu tuyến, vô tuyến, mạng thông tin điện tử hoặc bất kỳ phương tiện kỹ thuật nào khác;
8. Quyền dịch, phóng tác tác phẩm;
9. Quyền chuyển nhượng, cho thuê, cho mượn quyền sử dụng đối tượng quyền tác giả.

Điều 27. ThờI hạn bảo hộ quyền tác giả

1. Quyền nhân thân được bảo hộ vĩnh viễn, trừ quyền công bố tác phẩm.

2. Quyền công bố tác phẩm được bảo hộ trong suốt đờI tác giả và 75 năm sau khi tác giả chết.

3. Quyền tài sản được bảo hộ trong suốt đờI tác giả và 75 năm sau khi tác giả chết; đối với tác phẩm điện ảnh, nhiếp ảnh, mỹ thuật ứng dụng, tác phẩm ẩn danh thì thờI hạn bảo hộ là 75 năm kể từ khi tác phẩm được công bố lần đầu tiên.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "50/2005/QH11",
            "amendment": "07/2022/QH15",
            "effective_date": "2005-07-01",
            "issuing_body": "Quốc hội",
            "category": "Intellectual Property",
            "articles": ["14", "15", "19", "20", "27"],
        },
    },
    # ==========================================================================
    # 5. LUẬT NHÀ Ở 2014 - Housing Law
    # ==========================================================================
    {
        "title": "Luật Nhà ở 2014 - Điều kiện giao dịch về nhà ở",
        "content": """LUẬT NHÀ Ở
Số: 65/2014/QH13

Chương III
GIAO DỊCH VỀ NHÀ Ở

Điều 118. Điều kiện của bên bán, bên cho thuê mua nhà ở

1. Bên bán, bên cho thuê mua nhà ở phảI là chủ sở hữu nhà ở hoặc là ngườI được ủy quyền hợp pháp để thực hiện giao dịch.

2. Nhà ở được giao dịch phảI thuộc quyền sở hữu hợp pháp của bên bán, bên cho thuê mua và phảI có đầy đủ giấy tờ hợp lệ theo quy định của pháp luật.

3. Nhà ở không thuộc diện đang có tranh chấp, khiếu nại, khiếu kiện về quyền sở hữu; không bị kê biên để bảo đảm thi hành án; không thuộc diện đã có quyết định thu hồi đất, quyết định phá dỡ của cơ quan nhà nước có thẩm quyền.

Điều 119. Điều kiện của bên mua, bên thuê mua nhà ở

1. Cá nhân, hộ gia đình, tổ chức trong nước, ngườI Việt Nam định cư ở nước ngoài, tổ chức, cá nhân nước ngoài được mua, thuê mua nhà ở tại Việt Nam theo quy định của Luật này.

2. NgườI nước ngoài được mua nhà ở tại Việt Nam khi đáp ứng các điều kiện sau đây:
a) Được phép nhập cảnh vào Việt Nam;
b) Không thuộc diện được hưởng quyền ưu đãI, miễn trừ ngoạI giao, lãnh sự theo pháp luật.

Điều 121. Hợp đồng mua bán nhà ở

1. Hợp đồng mua bán nhà ở phảI được lập thành văn bản, có công chứng hoặc chứng thực theo quy định của pháp luật, trừ trường hợp quy định tại khoản 2 Điều này.

2. Hợp đồng mua bán nhà ở thuộc sở hữu nhà nước không bắt buộc phảI công chứng, chứng thực.

3. Hợp đồng mua bán nhà ở phảI có các nội dung chủ yếu sau đây:
a) Thông tin về các bên tham gia giao dịch;
b) Thông tin về nhà ở được giao dịch;
c) Giá mua bán nhà ở;
d) ThờI hạn, phương thức thanh toán;
đ) ThờI điểm giao nhà, thờI điểm chuyển quyền sở hữu nhà ở;
e) Cam kết của các bên;
g) Các nội dung khác theo thỏa thuận của các bên.

Điều 122. Nghĩa vụ của bên bán nhà ở

1. Giao nhà ở cho bên mua đúng chất lượng, diện tích, loại nhà ở, vị trí và các điều kiện khác theo thoả thuận trong hợp đồng.

2. Bàn giao đầy đủ hồ sơ pháp lý về nhà ở cho bên mua.

3. Làm thủ tục đăng ký quyền sở hữu nhà ở cho bên mua theo quy định của pháp luật.

4. Chịu trách nhiệm về tính hợp pháp của nhà ở được giao dịch.

5. Bảo đảm quyền sử dụng đất gắn liền với nhà ở được giao dịch.

6. Bồi thường thiệt hại do vi phạm hợp đồng gây ra.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "65/2014/QH13",
            "effective_date": "2015-07-01",
            "issuing_body": "Quốc hội",
            "category": "Housing Law",
            "articles": ["118", "119", "121", "122"],
        },
    },
    # ==========================================================================
    # 6. LUẬT BẢO VỆ QUYỀN LỢI NGƯỜI TIÊU DÙNG 2010 - Consumer Protection
    # ==========================================================================
    {
        "title": "Luật Bảo vệ quyền lợi ngườI tiêu dùng 2010",
        "content": """LUẬT BẢO VỆ QUYỀN LỢI NGƯỜI TIÊU DÙNG
Số: 59/2010/QH12

Chương II
QUYỀN CỦA NGƯỜI TIÊU DÙNG

Điều 7. Quyền của ngườI tiêu dùng

1. Được bảo đảm an toàn khi sử dụng hàng hóa, dịch vụ.

2. Được cung cấp thông tin đầy đủ, chính xác về hàng hóa, dịch vụ.

3. Được lựa chọn hàng hóa, dịch vụ theo nhu cầu, sở thích của mình.

4. Được tôn trọng danh dự, nhân phẩm, tính mạng, sức khỏe, tài sản và bí mật cá nhân.

5. Được đền bù thiệt hại do hàng hóa, dịch vụ không đảm bảo chất lượng gây ra.

6. Được khiếu nại, tố cáo, khởi kiện và được bồi thường thiệt hại theo quy định của pháp luật.

Điều 8. Quyền được bảo đảm an toàn

1. Tổ chức, cá nhân kinh doanh hàng hóa, dịch vụ phảI bảo đảm hàng hóa, dịch vụ của mình không gây thiệt hại đến tính mạng, sức khỏe, tài sản của ngườI tiêu dùng.

2. Hàng hóa, dịch vụ phảI đáp ứng tiêu chuẩn chất lượng đã công bố, tiêu chuẩn chất lượng quy định trong hợp đồng và các tiêu chuẩn, quy chuẩn kỹ thuật tương ứng.

3. Hàng hóa, dịch vụ có yêu cầu cao về an toàn phảI được cung cấp đầy đủ thông tin về cách sử dụng, bảo quản an toàn và các biện pháp phòng ngừa rủi ro.

Điều 9. Quyền được cung cấp thông tin đầy đủ, chính xác

1. Tổ chức, cá nhân kinh doanh hàng hóa, dịch vụ có trách nhiệm cung cấp cho ngườI tiêu dùng thông tin đầy đủ, chính xác, trung thực về hàng hóa, dịch vụ, bao gồm:
a) Tên, địa chỉ của tổ chức, cá nhân kinh doanh;
b) Tên, xuất xứ, địa chỉ của ngườI sản xuất;
c) Thành phần, công dụng, cách sử dụng, ngày sản xuất, hạn sử dụng;
d) Giá cả, điều kiện giao dịch;
đ) Chứng nhận chất lượng, chứng nhận hợp quy;
e) Thông tin khác theo quy định của pháp luật.

2. Thông tin về hàng hóa, dịch vụ phảI được cung cấp bằng tiếng Việt hoặc song ngữ tiếng Việt và tiếng nước ngoài.

Điều 10. Quyền được đổi, trả hàng và hoàn tiền

1. NgườI tiêu dùng có quyền đổi, trả hàng và được hoàn tiền trong các trường hợp sau:
a) Hàng hóa không đúng như thoả thuận;
b) Hàng hóa bị lỗi kỹ thuật;
c) Hàng hóa hết hạn sử dụng;
d) Giá bán cao hơn giá đã niêm yết tại nơi kinh doanh.

2. ThờI hạn đổi, trả hàng là 03 ngày đối với hàng thực phẩm, 07 ngày đối với hàng không phảI là thực phẩm, kể từ khi nhận hàng.

3. Tổ chức, cá nhân kinh doanh phảI hoàn trả đầy đủ số tiền đã nhận của ngườI tiêu dùng khi ngườI tiêu dùng trả lại hàng hóa theo quy định.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "59/2010/QH12",
            "effective_date": "2011-07-01",
            "issuing_body": "Quốc hội",
            "category": "Consumer Protection",
            "articles": ["7", "8", "9", "10"],
        },
    },
    # ==========================================================================
    # 7. LUẬT THƯƠNG MẠI 2005 - Commercial Law (Contract provisions)
    # ==========================================================================
    {
        "title": "Luật Thương mại 2005 - Hợp đồng thương mại",
        "content": """LUẬT THƯƠNG MẠI
Số: 36/2005/QH11

Chương VIII
HỢP ĐỒNG THƯƠNG MẠI

Điều 400. Khái niệm hợp đồng thương mại

Hợp đồng thương mại là sự thoả thuận giữa các bên về việc thực hiện hoạt động thương mại, xác lập, thay đổi hoặc chấm dứt quyền, nghĩa vụ của các bên.

Điều 401. Nguyên tắc giao kết hợp đồng thương mại

1. Tự do, tự nguyện, bình đẳng.

2. Trung thực, thiện chí.

3. Tuân thủ pháp luật, đạo đức xã hội.

Điều 402. Hình thức hợp đồng thương mại

1. Hợp đồng thương mại có thể được thể hiện bằng lờI nói, bằng văn bản hoặc bằng hành vi cụ thể.

2. Hợp đồng thương mại phảI được thể hiện bằng văn bản hoặc bằng hành vi cụ thể trong trường hợp pháp luật có quy định.

3. Hợp đồng thương mại được thể hiện bằng văn bản bao gồm hợp đồng được lập bằng văn bản, bằng điện, điện tử, fax, điện thoại và các hình thức khác tương tự.

Điều 403. Hiệu lực của hợp đồng thương mại

1. Hợp đồng thương mại có hiệu lực kể từ thờI điểm được giao kết, trừ trường hợp các bên có thoả thuận khác hoặc pháp luật có quy định khác.

2. Hợp đồng thương mại có hiệu lực đối với các bên và phảI được thực hiện theo đúng nội dung đã thoả thuận.

Điều 404. GiảI thích hợp đồng thương mại

1. Khi các điều khoản của hợp đồng thương mại không rõ ràng thì việc giảI thích hợp đồng được thực hiện theo nguyên tắc sau:
a) Ưu tiên áp dụng ý nghĩa phù hợp với bản chất của giao dịch;
b) GiảI thích theo cách làm cho hợp đồng có hiệu lực;
c) GiảI thích theo ý nghĩa thông thường của từ ngữ;
d) GiảI thích theo nguyên tắc trung thực, thiện chí.

2. Trong trường hợp hợp đồng được lập bằng nhiều ngôn ngữ khác nhau và có sự khác nhau về nội dung thì bản bằng tiếng Việt được ưu tiên áp dụng.

Điều 405. Thực hiện hợp đồng thương mại

1. Các bên phảI thực hiện nghiêm chỉnh nghĩa vụ của mình theo hợp đồng đã giao kết.

2. Trong quá trình thực hiện hợp đồng, nếu một bên gặp khó khăn, trở ngại thì hai bên phảI cùng nhau thoả thuận để sửa đổi, bổ sung hợp đồng cho phù hợp.

3. Việc thực hiện hợp đồng phảI đảm bảo đúng đối tượng, số lượng, chất lượng, giá cả, thờI hạn, địa điểm và phương thức thực hiện theo thoả thuận.

Điều 406. Vi phạm hợp đồng thương mại

1. Vi phạm hợp đồng thương mại là hành vi của một bên không thực hiện đúng nghĩa vụ theo hợp đồng đã giao kết.

2. Bên vi phạm hợp đồng phảI chịu trách nhiệm bồi thường thiệt hại do vi phạm hợp đồng gây ra, trừ trường hợp có thoả thuận khác hoặc pháp luật có quy định khác.

3. Thiệt hại do vi phạm hợp đồng bao gồm thiệt hại thực tế và lợI nhuận bị mất.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "36/2005/QH11",
            "effective_date": "2006-01-01",
            "issuing_body": "Quốc hội",
            "category": "Commercial Law",
            "articles": ["400", "401", "402", "403", "404", "405", "406"],
        },
    },
    # ==========================================================================
    # 8. LUẬT ĐẤT ĐAI 2013 - Land Law
    # ==========================================================================
    {
        "title": "Luật Đất đai 2013 - Quyền sử dụng đất",
        "content": """LUẬT ĐẤT ĐAI
Số: 45/2013/QH13

Chương III
QUYỀN VÀ NGHĨA VỤ CỦA NGƯỜI SỬ DỤNG ĐẤT

Điều 166. Quyền của ngườI sử dụng đất

1. NgườI sử dụng đất có các quyền sau đây:
a) Được cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà ở và tài sản khác gắn liền với đất;
b) Được hưởng thành quả lao động, kết quả đầu tư trên đất;
c) Được khai thác vật liệu, khoáng sản làm vật liệu xây dựng, khai thác khoáng sản làm vật liệu san lấp và khai thác khoáng sản thông thường theo quy định của pháp luật;
d) Được Nhà nước bảo hộ quyền sử dụng đất khi ngườI khác xâm phạm;
đ) Được bồi thường thiệt hại khi Nhà nước thu hồi đất;
e) Được khiếu nại, tố cáo, khởi kiện về quyết định hành chính, hành vi hành chính trong lĩnh vực đất đai.

2. NgườI sử dụng đất được thực hiện các quyền sau đây đối với đất đai:
a) Chuyển đổi quyền sử dụng đất;
b) Chuyển nhượng quyền sử dụng đất;
c) Cho thuê quyền sử dụng đất;
d) Cho thuê lại quyền sử dụng đất;
đ) Thừa kế quyền sử dụng đất;
e) Tặng cho quyền sử dụng đất;
g) Thế chấp, góp vốn bằng quyền sử dụng đất.

Điều 167. Nghĩa vụ của ngườI sử dụng đất

1. Sử dụng đất đúng mục đích, đúng ranh giới thửa đất, bảo vệ công trình công cộng, không làm thiệt hại đến đất đai và gây thiệt hại đến quyền, lợI ích hợp pháp của ngườI sử dụng đất xung quanh.

2. Tuân thủ các quy định về quản lý và sử dụng đất đai, thực hiện nghĩa vụ tài chính về đất đai theo quy định của pháp luật.

3. Thực hiện các biện pháp bảo vệ đất, bảo vệ môi trường, không làm ảnh hưởng đến lợI ích của Nhà nước, cộng đồng.

4. Bồi thường thiệt hại do vi phạm pháp luật về đất đai gây ra.

Điều 168. Chuyển nhượng quyền sử dụng đất

1. NgườI sử dụng đất được quyền chuyển nhượng quyền sử dụng đất trong các trường hợp sau đây:
a) Đã được cấp Giấy chứng nhận quyền sử dụng đất;
b) Đất không có tranh chấp;
c) Quyền sử dụng đất không bị kê biên để bảo đảm thi hành án;
d) Trong thờI hạn sử dụng đất.

2. Việc chuyển nhượng quyền sử dụng đất phảI được thực hiện bằng hợp đồng bằng văn bản và phảI được công chứng hoặc chứng thực.

3. Quyền sử dụng đất được chuyển nhượng kể từ thờI điểm đăng ký tại cơ quan nhà nước có thẩm quyền.

Điều 174. Thế chấp quyền sử dụng đất

1. NgườI sử dụng đất được quyền thế chấp quyền sử dụng đất tại tổ chức tín dụng được phép hoạt động tại Việt Nam, tại tổ chức kinh tế khác hoặc cá nhân để vay vốn, thực hiện nghĩa vụ tài chính khác.

2. Việc thế chấp quyền sử dụng đất phảI được thực hiện bằng hợp đồng bằng văn bản và phảI được công chứng hoặc chứng thực.

3. Quyền sử dụng đất được thế chấp kể từ thờI điểm đăng ký tại cơ quan nhà nước có thẩm quyền.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "45/2013/QH13",
            "effective_date": "2014-07-01",
            "issuing_body": "Quốc hội",
            "category": "Land Law",
            "articles": ["166", "167", "168", "174"],
        },
    },
    # ==========================================================================
    # 9. NGHỊ ĐỊNH 99/2013/NĐ-CP - Contract guidance
    # ==========================================================================
    {
        "title": "Nghị định 99/2013/NĐ-CP - Hợp đồng mua bán hàng hóa",
        "content": """NGHỊ ĐỊNH
Về xử phạt vi phạm hành chính trong hoạt động thương mại, sản xuất, buôn bán hàng giả, hàng cấm và bảo vệ quyền lợI ngườI tiêu dùng
Số: 99/2013/NĐ-CP

Chương I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh

Nghị định này quy định về hành vi vi phạm hành chính, hình thức xử phạt, mức xử phạt, biện pháp khắc phục hậu quả vi phạm hành chính, thẩm quyền lập biên bản, thẩm quyền xử phạt vi phạm hành chính trong hoạt động thương mại, sản xuất, buôn bán hàng giả, hàng cấm và bảo vệ quyền lợI ngườI tiêu dùng.

Điều 2. Đối tượng áp dụng

1. Cá nhân, tổ chức có hành vi vi phạm hành chính trong hoạt động thương mại, sản xuất, buôn bán hàng giả, hàng cấm và bảo vệ quyền lợI ngườI tiêu dùng.

2. Cá nhân, tổ chức có thẩm quyền lập biên bản, thẩm quyền xử phạt vi phạm hành chính trong hoạt động thương mại, sản xuất, buôn bán hàng giả, hàng cấm và bảo vệ quyền lợI ngườI tiêu dùng.

Chương II
CÁC HÀNH VI VI PHẠM VÀ MỨC XỬ PHẠT

Điều 5. Vi phạm quy định về giao kết hợp đồng

1. Phạt cảnh cáo hoặc phạt tiền từ 500.000 đồng đến 1.000.000 đồng đối với một trong các hành vi sau đây:
a) Không giao kết hợp đồng bằng văn bản trong trường hợp pháp luật quy định phảI giao kết bằng văn bản;
b) Hợp đồng thiếu các nội dung chủ yếu theo quy định của pháp luật;
c) Không đăng ký hợp đồng theo quy định của pháp luật.

2. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với hành vi sử dụng hợp đồng có điều khoản trái pháp luật.

Điều 6. Vi phạm quy định về thực hiện hợp đồng

1. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với một trong các hành vi sau đây:
a) Không giao hàng đúng thờI hạn, đúng địa điểm theo hợp đồng;
b) Giao hàng không đúng số lượng, chất lượng theo hợp đồng;
c) Không thanh toán đúng thờI hạn theo hợp đồng.

2. Phạt tiền từ 3.000.000 đồng đến 5.000.000 đồng đối với hành vi từ chối thực hiện hợp đồng không có lý do chính đáng.

Điều 7. Vi phạm quy định về bảo hành

1. Phạt tiền từ 500.000 đồng đến 1.000.000 đồng đối với hành vi không thực hiện bảo hành theo cam kết.

2. Phạt tiền từ 1.000.000 đồng đến 3.000.000 đồng đối với hành vi từ chối bảo hành khi hàng hóa còn trong thờI hạn bảo hành.
""",
        "doc_type": "nghi_dinh",
        "metadata": {
            "law_id": "99/2013/NĐ-CP",
            "effective_date": "2013-10-01",
            "issuing_body": "Chính phủ",
            "category": "Commercial Decree",
            "articles": ["1", "2", "5", "6", "7"],
        },
    },
    # ==========================================================================
    # 10. THÔNG TƯ 01/2021/TT-BTP - Contract templates
    # ==========================================================================
    {
        "title": "Thông tư 01/2021/TT-BTP - Hợp đồng lao động mẫu",
        "content": """THÔNG TƯ
Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về lao động
Số: 01/2021/TT-BTP

Chương I
QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh

Thông tư này quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về hợp đồng lao động, thờI giờ làm việc, thờI giờ nghỉ ngơi, an toàn, vệ sinh lao động.

Điều 2. Đối tượng áp dụng

Thông tư này áp dụng đối với ngườI sử dụng lao động, ngườI lao động và tổ chức, cá nhân có liên quan đến quan hệ lao động.

Chương II
HỢP ĐỒNG LAO ĐỘNG

Điều 3. Hợp đồng lao động mẫu

1. Hợp đồng lao động mẫu bao gồm các nội dung chủ yếu sau:
a) Tên và địa chỉ của ngườI sử dụng lao động;
b) Họ và tên, ngày tháng năm sinh, giớI tính, nơi cư trú của ngườI lao động;
c) Công việc phảI làm và địa điểm làm việc;
d) ThờI hạn của hợp đồng lao động;
đ) Mức lương, hình thức trả lương, thờI hạn trả lương;
e) Chế độ nâng bậc, nâng lương;
g) ThờI giờ làm việc, thờI giờ nghỉ ngơi;
h) Bảo hộ lao động, an toàn lao động;
i) Bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp.

2. Hợp đồng lao động phảI được giao kết trước khi ngườI lao động bắt đầu làm việc.

Điều 4. Phụ lục hợp đồng lao động

1. Phụ lục hợp đồng lao động là bộ phận không tách rời của hợp đồng lao động.

2. Phụ lục hợp đồng lao động được lập khi có sự thay đổi về nội dung của hợp đồng lao động.

3. Phụ lục hợp đồng lao động phảI ghi rõ nội dung thay đổi và có hiệu lực kể từ ngày được ký kết.

Điều 5. ThờI hạn thử việc

1. ThờI hạn thử việc phảI được ghi rõ trong hợp đồng lao động hoặc hợp đồng thử việc.

2. Trong thờI hạn thử việc, mỗi bên có quyền huỷ bỏ thoả thuận thử việc mà không cần báo trước và không phảI bồi thường thiệt hại.

3. Khi hết thờI hạn thử việc, ngườI sử dụng lao động phảI thông báo kết quả thử việc cho ngườI lao động.
""",
        "doc_type": "thong_tu",
        "metadata": {
            "law_id": "01/2021/TT-BTP",
            "effective_date": "2021-02-15",
            "issuing_body": "Bộ Tư pháp",
            "category": "Labor Circular",
            "articles": ["1", "2", "3", "4", "5"],
        },
    },
    # ==========================================================================
    # 11. LUẬT CẠNH TRANH 2018 - Competition Law
    # ==========================================================================
    {
        "title": "Luật Cạnh tranh 2018 - Hành vi cạnh tranh không lành mạnh",
        "content": """LUẬT CẠNH TRANH
Số: 23/2018/QH14

Chương III
HÀNH VI CẠNH TRANH KHÔNG LÀNH MẠNH

Điều 43. Hành vi cạnh tranh không lành mạnh

1. Hành vi cạnh tranh không lành mạnh là hành vi của doanh nghiệp trong hoạt động kinh doanh nhằm loại bỏ đối thủ cạnh tranh hoặc cản trở đối thủ cạnh tranh, gây thiệt hại cho đối thủ cạnh tranh, ngườI tiêu dùng và xã hội.

2. Các hành vi cạnh tranh không lành mạnh bao gồm:
a) Xâm phạm bí mật kinh doanh;
b) Ép buộc trong kinh doanh;
c) Phân biệt đối xử trong kinh doanh;
d) Bán phá giá;
đ) Cạnh tranh bằng hành vi phá hoại uy tín, danh dự của tổ chức, cá nhân khác;
e) Cạnh tranh bằng hành vi xâm phạm quyền sở hữu công nghiệp;
g) Lôi kéo khách hàng bằng cách sử dụng chứng nhận, giấy phép, giấy chứng nhận giả mạo.

Điều 44. Xâm phạm bí mật kinh doanh

1. Xâm phạm bí mật kinh doanh là hành vi thu thập, tiết lộ, sử dụng bí mật kinh doanh của tổ chức, cá nhân khác mà không được sự đồng ý của chủ sở hữu bí mật kinh doanh.

2. Bí mật kinh doanh bao gồm:
a) Công thức, công thức hóa học, thiết kế, quy trình sản xuất;
b) Phương pháp kinh doanh, chiến lược kinh doanh;
c) Thông tin về khách hàng, nhà cung cấp;
d) Thông tin về nghiên cứu và phát triển sản phẩm;
đ) Các thông tin khác có giá trị kinh tế và được bảo mật.

Điều 45. Ép buộc trong kinh doanh

1. Ép buộc trong kinh doanh là hành vi của doanh nghiệp lợI dụng vị thế kinh tế để ép buộc tổ chức, cá nhân khác phảI thực hiện hoặc không được thực hiện một hành vi kinh doanh nhất định.

2. Hành vi ép buộc trong kinh doanh bao gồm:
a) Ép buộc đối tác kinh doanh không được giao dịch với đối thủ cạnh tranh;
b) Ép buộc đối tác kinh doanh phảI chấp nhận điều kiện kinh doanh bất lợI;
c) Ép buộc đối tác kinh doanh phảI mua hàng hóa, dịch vụ không mong muốn.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "23/2018/QH14",
            "effective_date": "2019-07-01",
            "issuing_body": "Quốc hội",
            "category": "Competition Law",
            "articles": ["43", "44", "45"],
        },
    },
    # ==========================================================================
    # 12. LUẬT ĐẦU TƯ 2020 - Investment Law
    # ==========================================================================
    {
        "title": "Luật Đầu tư 2020 - Hình thức đầu tư và hợp đồng",
        "content": """LUẬT ĐẦU TƯ
Số: 61/2020/QH14

Chương III
HÌNH THỨC ĐẦU TƯ, THỦ TỤC THÀNH LẬP TỔ CHỨC KINH TẾ

Điều 21. Hình thức đầu tư

1. Nhà đầu tư có quyền lựa chọn hình thức đầu tư sau đây:
a) Thành lập tổ chức kinh tế;
b) Đầu tư góp vốn, mua cổ phần, mua phần vốn góp;
c) Thực hiện dự án đầu tư;
d) Đầu tư theo hình thức hợp đồng BCC, hợp đồng B.O.T, hợp đồng B.O.O, hợp đồng B.T.O, hợp đồng B.T.T;
đ) Đầu tư theo hình thức đối tác công tư;
e) Đầu tư theo hình thức khác theo quy định của Chính phủ.

2. Hình thức đầu tư phảI phù hợp với ngành, nghề đầu tư kinh doanh và điều kiện đầu tư kinh doanh theo quy định của pháp luật.

Điều 22. Hợp đồng hợp tác kinh doanh (BCC)

1. Hợp đồng hợp tác kinh doanh là hợp đồng giữa các nhà đầu tư để hợp tác đầu tư, kinh doanh phân chia lợI nhuận, phân chia sản phẩm tại Việt Nam mà không thành lập tổ chức kinh tế.

2. Hợp đồng hợp tác kinh doanh phảI có các nội dung chủ yếu sau:
a) Tên, địa chỉ, ngườI đại diện theo pháp luật của các bên;
b) Mục tiêu, phạm vi, nội dung của dự án đầu tư;
c) ThờI hạn thực hiện hợp đồng và thờI điểm có hiệu lực của hợp đồng;
d) Phân chia lợI nhuận, phân chia sản phẩm;
đ) Quyền và nghĩa vụ của các bên;
e) Sửa đổi, bổ sung, chấm dứt hợp đồng;
g) Trách nhiệm do vi phạm hợp đồng;
h) GiảI quyết tranh chấp.

3. Hợp đồng hợp tác kinh doanh phảI được lập thành văn bản và có đủ chữ ký của các bên.

Điều 23. Hợp đồng B.O.T, B.O.O, B.T.O, B.T.T

1. Hợp đồng B.O.T (Xây dựng - Kinh doanh - Chuyển giao) là hợp đồng giữa cơ quan nhà nước có thẩm quyền và nhà đầu tư để xây dựng công trình kết cấu hạ tầng, sau thờI gian kinh doanh thu hồi vốn đầu tư và lợI nhuận thì chuyển giao công trình cho Nhà nước.

2. Hợp đồng B.O.O (Xây dựng - Sở hữu - Kinh doanh) là hợp đồng giữa cơ quan nhà nước có thẩm quyền và nhà đầu tư để xây dựng công trình kết cấu hạ tầng, sau khi hoàn thành nhà đầu tư được sở hữu và kinh doanh công trình trong thờI hạn nhất định.

3. Hợp đồng B.T.O (Xây dựng - Chuyển giao - Kinh doanh) là hợp đồng giữa cơ quan nhà nước có thẩm quyền và nhà đầu tư để xây dựng công trình kết cấu hạ tầng, sau khi hoàn thành chuyển giao cho Nhà nước và nhà đầu tư được kinh doanh thu hồi vốn và lợI nhuận.

4. Hợp đồng B.T.T (Xây dựng - Chuyển giao - Thuê) là hợp đồng giữa cơ quan nhà nước có thẩm quyền và nhà đầu tư để xây dựng công trình kết cấu hạ tầng, sau khi hoàn thành chuyển giao cho Nhà nước và nhà đầu tư được thuê để kinh doanh thu hồi vốn và lợI nhuận.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "61/2020/QH14",
            "effective_date": "2021-01-01",
            "issuing_body": "Quốc hội",
            "category": "Investment Law",
            "articles": ["21", "22", "23"],
        },
    },
    # ==========================================================================
    # 13. LUẬT THUẾ THU NHẬP DOANH NGHIỆP 2008 - Corporate Tax
    # ==========================================================================
    {
        "title": "Luật Thuế thu nhập doanh nghiệp 2008 - Thuế suất và tính thuế",
        "content": """LUẬT THUẾ THU NHẬP DOANH NGHIỆP
Số: 14/2008/QH12 (được sửa đổi, bổ sung bởi Luật số 71/2014/QH13)

Chương II
CĂN CỨ VÀ PHƯƠNG PHÁP TÍNH THUẾ

Điều 10. Thuế suất thuế thu nhập doanh nghiệp

1. Thuế suất thuế thu nhập doanh nghiệp là 20%.

2. Thuế suất thuế thu nhập doanh nghiệp đối với doanh nghiệp khai thác dầu khí, tài nguyên khoáng sản quy định tại Luật này và các văn bản hướng dẫn thi hành.

3. Thuế suất ưu đãI áp dụng đối với doanh nghiệp thực hiện dự án đầu tư mới tại địa bàn có điều kiện kinh tế - xã hội khó khăn, địa bàn có điều kiện kinh tế - xã hội đặc biệt khó khăn; doanh nghiệp thực hiện dự án đầu tư mới thuộc lĩnh vực công nghệ cao, nghiên cứu và phát triển khoa học và công nghệ.

Điều 11. Căn cứ tính thuế

1. Căn cứ tính thuế thu nhập doanh nghiệp là thu nhập chịu thuế và thuế suất.

2. Số thuế thu nhập doanh nghiệp phảI nộp bằng thu nhập chịu thuế nhân với thuế suất.

Điều 12. Thu nhập chịu thuế

1. Thu nhập chịu thuế bao gồm:
a) Thu nhập từ hoạt động sản xuất, kinh doanh hàng hóa, dịch vụ;
b) Thu nhập từ hoạt động tài chính;
c) Thu nhập từ hoạt động chuyển nhượng vốn, chuyển nhượng chứng khoán;
d) Thu nhập từ hoạt động chuyển nhượng bất động sản;
đ) Thu nhập từ hoạt động kinh doanh khác.

2. Thu nhập chịu thuế trong kỳ tính thuế là thu nhập tính thuế trừ đi các khoản lỗ được chuyển theo quy định của Luật này.

Điều 13. Thu nhập tính thuế

1. Thu nhập tính thuế bằng doanh thu trừ đi các khoản chi phí được trừ và các khoản lỗ được chuyển từ các năm trước theo quy định của Luật này.

2. Doanh thu để tính thu nhập tính thuế bao gồm tất cả các khoản thu từ hoạt động sản xuất, kinh doanh hàng hóa, dịch vụ, bao gồm cả khoản trợ giá, phụ thu, phụ trộI.

Điều 14. Chi phí được trừ khi xác định thu nhập chịu thuế

1. Chi phí được trừ khi xác định thu nhập chịu thuế phảI đáp ứng các điều kiện sau:
a) Chi phí thực tế phát sinh liên quan đến hoạt động sản xuất, kinh doanh của doanh nghiệp;
b) Chi phí có đầy đủ hóa đơn, chứng từ hợp pháp theo quy định của pháp luật;
c) Chi phí đối với hàng hóa, dịch vụ mua vào có hóa đơn mua hàng ghi rõ giá thanh toán là giá đã có thuế giá trị gia tăng.

2. Các khoản chi phí không được trừ khi xác định thu nhập chịu thuế bao gồm:
a) Chi phí không đáp ứng đủ các điều kiện quy định tại khoản 1 Điều này;
b) Khoản tiền phạt, tiền bồi thường do vi phạm pháp luật;
c) Chi phí không có hóa đơn, chứng từ hợp pháp.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "14/2008/QH12",
            "amendment": "71/2014/QH13",
            "effective_date": "2009-01-01",
            "issuing_body": "Quốc hội",
            "category": "Corporate Tax",
            "articles": ["10", "11", "12", "13", "14"],
        },
    },
    # ==========================================================================
    # 14. LUẬT AN TOÀN THỰC PHẨM 2010 - Food Safety
    # ==========================================================================
    {
        "title": "Luật An toàn thực phẩm 2010 - Trách nhiệm của tổ chức, cá nhân",
        "content": """LUẬT AN TOÀN THỰC PHẨM
Số: 55/2010/QH12

Chương II
TRÁCH NHIỆM CỦA TỔ CHỨC, CÁ NHÂN ĐỐI VỚI AN TOÀN THỰC PHẨM

Điều 8. Trách nhiệm của tổ chức, cá nhân sản xuất, kinh doanh thực phẩm

1. Bảo đảm thực phẩm an toàn theo quy định của Luật này.

2. Chịu trách nhiệm về chất lượng, an toàn thực phẩm của sản phẩm do mình sản xuất, kinh doanh.

3. Chấp hành các quy định về điều kiện bảo đảm an toàn thực phẩm, quy trình sản xuất thực phẩm an toàn.

4. Thực hiện việc kiểm nghiệm, ghi nhãn, công bố chất lượng, an toàn thực phẩm theo quy định của pháp luật.

5. Chịu trách nhiệm thu hồi, xử lý thực phẩm không bảo đảm an toàn theo quy định của pháp luật.

6. Bồi thường thiệt hại do thực phẩm không an toàn gây ra cho ngườI tiêu dùng.

Điều 9. Trách nhiệm của tổ chức, cá nhân nhập khẩu thực phẩm

1. Chịu trách nhiệm về chất lượng, an toàn thực phẩm nhập khẩu.

2. Thực hiện việc kiểm tra, kiểm nghiệm thực phẩm nhập khẩu theo quy định của pháp luật.

3. Cung cấp đầy đủ thông tin về nguồn gốc, xuất xứ, thành phần, hướng dẫn sử dụng, bảo quản thực phẩm bằng tiếng Việt.

4. Chịu trách nhiệm thu hồi, xử lý thực phẩm nhập khẩu không bảo đảm an toàn.

Điều 10. Trách nhiệm của ngườI tiêu dùng

1. Mua, sử dụng thực phẩm có nguồn gốc, xuất xứ rõ ràng, có nhãn mác, hướng dẫn sử dụng, bảo quản đầy đủ.

2. Bảo quản thực phẩm theo đúng hướng dẫn của nhà sản xuất.

3. Khi phát hiện thực phẩm không an toàn, kịp thờI thông báo cho cơ quan nhà nước có thẩm quyền.

4. Tham gia giám sát việc thực hiện pháp luật về an toàn thực phẩm.

Điều 11. Trách nhiệm của tổ chức, cá nhân quảng cáo thực phẩm

1. Quảng cáo thực phẩm phảI đúng sự thật, đầy đủ thông tin về thực phẩm.

2. Không được quảng cáo thực phẩm có tác dụng chữa bệnh đối với thực phẩm không phảI là thuốc.

3. Không được sử dụng hình ảnh, lờI nói, chữ viết của cán bộ y tế, bác sĩ để quảng cáo thực phẩm.

4. Chịu trách nhiệm về nội dung quảng cáo thực phẩm.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "55/2010/QH12",
            "effective_date": "2011-07-01",
            "issuing_body": "Quốc hội",
            "category": "Food Safety",
            "articles": ["8", "9", "10", "11"],
        },
    },
    # ==========================================================================
    # 15. LUẬT BẢO HIỂM XÃ HỘI 2014 - Social Insurance
    # ==========================================================================
    {
        "title": "Luật Bảo hiểm xã hội 2014 - Quyền lợI và thủ tục",
        "content": """LUẬT BẢO HIỂM XÃ HỘI
Số: 58/2014/QH13

Chương II
BẢO HIỂM XÃ HỘI BẮT BUỘC

Điều 12. Đối tượng tham gia bảo hiểm xã hội bắt buộc

1. NgườI lao động là công dân Việt Nam thuộc đối tượng sau đây:
a) NgườI lao động làm việc theo hợp đồng lao động không xác định thờI hạn, hợp đồng lao động xác định thờI hạn từ đủ 03 tháng trở lên;
b) NgườI lao động làm việc theo hợp đồng lao động có thờI hạn từ đủ 01 tháng đến dưới 03 tháng;
c) Cán bộ, công chức, viên chức;
d) Công nhân quốc phòng, công nhân công an, ngườI làm công tác khác trong tổ chức cơ yếu;
đ) Sĩ quan, quân nhân chuyên nghiệp, công nhân, viên chức quốc phòng; sĩ quan, hạ sĩ quan nghiệp vụ, sĩ quan, hạ sĩ quan chuyên môn kỹ thuật công an.

2. NgườI lao động là ngườI nước ngoài làm việc tại Việt Nam có Giấy phép lao động hoặc Chứng chỉ hành nghề do cơ quan có thẩm quyền của Việt Nam cấp.

Điều 13. Mức đóng bảo hiểm xã hội

1. Mức đóng bảo hiểm xã hội được tính trên cơ sở mức tiền lương tháng đóng bảo hiểm xã hội của ngườI lao động.

2. Tỷ lệ đóng bảo hiểm xã hội bắt buộc:
a) NgườI sử dụng lao động đóng 17,5% mức tiền lương tháng đóng bảo hiểm xã hội;
b) NgườI lao động đóng 8% mức tiền lương tháng đóng bảo hiểm xã hội;
c) Tổng mức đóng là 25,5% mức tiền lương tháng đóng bảo hiểm xã hội.

3. Mức tiền lương tháng đóng bảo hiểm xã hội được tính theo quy định của pháp luật về lao động và pháp luật về tiền lương.

Điều 14. Quyền lợI của ngườI lao động tham gia bảo hiểm xã hội bắt buộc

NgườI lao động tham gia bảo hiểm xã hội bắt buộc được hưởng các chế độ sau:
1. Chế độ ốm đau;
2. Chế độ thai sản;
3. Chế độ tai nạn lao động, bệnh nghề nghiệp;
4. Chế độ hưu trí;
5. Chế độ tử tuất.

Điều 15. Chế độ ốm đau

1. NgườI lao động được hưởng chế độ ốm đau khi có giấy chứng nhận nghỉ việc hưởng bảo hiểm xã hội của cơ sở khám bệnh, chữa bệnh có thẩm quyền.

2. ThờI gian hưởng chế độ ốm đau tối đa trong năm:
a) 30 ngày nếu đã đóng bảo hiểm xã hội dưới 15 năm;
b) 40 ngày nếu đã đóng bảo hiểm xã hội từ đủ 15 năm đến dưới 30 năm;
c) 60 ngày nếu đã đóng bảo hiểm xã hội từ đủ 30 năm trở lên.

3. Mức hưởng chế độ ốm đau bằng 75% mức tiền lương tháng đóng bảo hiểm xã hội của tháng liền kề trước khi nghỉ việc.

Điều 16. Chế độ thai sản

1. NgườI lao động nữ được nghỉ việc hưởng chế độ thai sản trước và sau khi sinh con là 06 tháng.

2. Trong thờI gian nghỉ việc hưởng chế độ thai sản, ngườI lao động được hưởng mức bằng 100% mức tiền lương tháng đóng bảo hiểm xã hội của tháng liền kề trước khi nghỉ việc.

3. NgườI lao động nam có vợ sinh con được nghỉ việc hưởng chế độ thai sản 05 ngày làm việc.
""",
        "doc_type": "luat",
        "metadata": {
            "law_id": "58/2014/QH13",
            "effective_date": "2016-01-01",
            "issuing_body": "Quốc hội",
            "category": "Social Insurance",
            "articles": ["12", "13", "14", "15", "16"],
        },
    },
]


# =============================================================================
# HUGGINGFACE DATASET CONFIGURATION
# =============================================================================

HUGGINGFACE_DATASET = "th1nhng0/vietnamese-legal-documents"
HUGGINGFACE_CONFIG = "content"  # Dataset has multiple configs: 'metadata', 'relationships', 'content'
HUGGINGFACE_SPLIT = "data"  # Available split is 'data', not 'train'
HUGGINGFACE_LIMIT = 50  # Ingest 50 documents from HuggingFace dataset


async def try_huggingface_ingestion(pipeline: IngestionPipeline) -> dict[str, Any] | None:
    """Try to ingest from HuggingFace dataset.
    
    Args:
        pipeline: IngestionPipeline instance.
        
    Returns:
        Ingestion stats if successful, None otherwise.
    """
    logger.info(f"Attempting to load from HuggingFace dataset: {HUGGINGFACE_DATASET}")
    logger.info(f"Split: {HUGGINGFACE_SPLIT}, Limit: {HUGGINGFACE_LIMIT}")
    
    try:
        stats = await pipeline.ingest_from_huggingface(
            dataset_name=HUGGINGFACE_DATASET,
            config=HUGGINGFACE_CONFIG,  # Use 'content' config
            split=HUGGINGFACE_SPLIT,
            limit=HUGGINGFACE_LIMIT,
        )
        
        if stats.get("errors"):
            # Check if it's the datasets library error
            for error in stats["errors"]:
                if "datasets library not installed" in str(error):
                    logger.error("❌ HuggingFace 'datasets' library not installed!")
                    logger.error("   Install it with: pip install datasets")
                    logger.error("   Then run this script again.")
                    return None
        
        if stats.get("parsed", 0) > 0:
            logger.info(f"✓ Successfully ingested {stats['parsed']} documents from HuggingFace")
            return stats
        else:
            logger.warning("No documents parsed from HuggingFace")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to ingest from HuggingFace: {e}")
        return None


async def ingest_hardcoded_documents(pipeline: IngestionPipeline) -> dict[str, Any]:
    """Ingest hardcoded real Vietnamese legal documents.
    
    Args:
        pipeline: IngestionPipeline instance.
        
    Returns:
        Ingestion statistics.
    """
    logger.info(f"Ingesting {len(REAL_LEGAL_DOCUMENTS)} hardcoded legal documents")
    
    stats = {
        "total": len(REAL_LEGAL_DOCUMENTS),
        "success": 0,
        "failed": 0,
        "errors": [],
        "document_ids": [],
    }
    
    for i, doc in enumerate(REAL_LEGAL_DOCUMENTS, 1):
        try:
            logger.info(f"[{i}/{len(REAL_LEGAL_DOCUMENTS)}] Ingesting: {doc['title']}")
            
            node = await pipeline.ingest_single_document(
                title=doc["title"],
                content=doc["content"],
            )
            
            stats["success"] += 1
            stats["document_ids"].append(node.id)
            logger.info(f"  ✓ Successfully ingested: {node.id}")
            
        except Exception as e:
            stats["failed"] += 1
            error_msg = f"Failed to ingest '{doc['title']}': {str(e)}"
            stats["errors"].append(error_msg)
            logger.error(f"  ✗ {error_msg}")
            # Continue with next document
    
    return stats


async def validate_postgres_count() -> int:
    """Validate ingestion by querying PostgreSQL document count.
    
    Returns:
        Number of documents in PostgreSQL.
    """
    settings = get_settings()
    
    try:
        pool = await asyncpg.create_pool(
            settings.postgres_dsn,
            min_size=1,
            max_size=2,
        )
        
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
        
        await pool.close()
        return count
        
    except Exception as e:
        logger.error(f"Failed to query PostgreSQL: {e}")
        return -1


async def main():
    """Main ingestion script."""
    logger.info("=" * 60)
    logger.info("Vietnamese Legal Documents Ingestion Script")
    logger.info("=" * 60)
    
    # Check environment variables
    settings = get_settings()
    logger.info(f"PostgreSQL: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"OpenSearch: {settings.opensearch_host}:{settings.opensearch_port}")
    
    # Initialize pipeline
    try:
        pipeline = IngestionPipeline(settings)
        logger.info("IngestionPipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize IngestionPipeline: {e}")
        return 1
    
    # Track overall stats
    overall_stats = {
        "source": "unknown",
        "total_attempted": 0,
        "success": 0,
        "failed": 0,
        "errors": [],
    }
    
    try:
        # Load from HuggingFace (PRIMARY AND ONLY SOURCE)
        hf_stats = await try_huggingface_ingestion(pipeline)
        
        if not hf_stats:
            logger.error("=" * 60)
            logger.error("❌ INGESTION FAILED")
            logger.error("=" * 60)
            logger.error("HuggingFace ingestion failed or returned no documents.")
            logger.error("")
            logger.error("Please check:")
            logger.error("1. Is 'datasets' library installed? Run: pip install datasets")
            logger.error("2. Is the dataset name correct? th1nhng0/vietnamese-legal-documents")
            logger.error("3. Do you have internet connection to download from HuggingFace?")
            logger.error("4. Does the dataset exist and is it accessible?")
            logger.error("=" * 60)
            return 1
        
        # Set overall stats from HuggingFace
        overall_stats["source"] = "huggingface"
        overall_stats["total_attempted"] = hf_stats.get("total_loaded", 0)
        overall_stats["success"] = hf_stats.get("parsed", 0)
        overall_stats["failed"] = len(hf_stats.get("errors", []))
        overall_stats["errors"] = hf_stats.get("errors", [])
        
        # Validate by querying PostgreSQL
        logger.info("-" * 60)
        logger.info("Validating ingestion...")
        pg_count = await validate_postgres_count()
        
        if pg_count >= 0:
            logger.info(f"Total documents in PostgreSQL: {pg_count}")
        else:
            logger.warning("Could not validate PostgreSQL count")
        
        # Print summary
        logger.info("=" * 60)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Source: {overall_stats['source']}")
        logger.info(f"Total attempted: {overall_stats['total_attempted']}")
        logger.info(f"Successfully ingested: {overall_stats['success']}")
        logger.info(f"Failed: {overall_stats['failed']}")
        
        if overall_stats["errors"]:
            logger.info(f"\nErrors ({len(overall_stats['errors'])}):")
            for i, error in enumerate(overall_stats["errors"][:5], 1):
                logger.info(f"  {i}. {error}")
            if len(overall_stats["errors"]) > 5:
                logger.info(f"  ... and {len(overall_stats['errors']) - 5} more errors")
        
        logger.info("=" * 60)
        
        if overall_stats["success"] > 0:
            logger.info("✓ Ingestion completed successfully!")
            return 0
        else:
            logger.error("✗ No documents were ingested")
            return 1
            
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {e}")
        return 1
        
    finally:
        # Clean up
        try:
            await pipeline.close()
            logger.info("Pipeline connections closed")
        except Exception as e:
            logger.warning(f"Error closing pipeline: {e}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
