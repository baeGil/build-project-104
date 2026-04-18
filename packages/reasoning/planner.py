"""Query planner for transforming raw user queries into structured QueryPlan objects."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from packages.common.types import QueryPlan, QueryStrategy


# =============================================================================
# CONSTANTS
# =============================================================================

LEGAL_ABBREVIATIONS: dict[str, str] = {
    # Core Legal Codes
    "BLHS": "Bộ Luật Hình Sự",
    "BLDS": "Bộ Luật Dân Sự",
    "BLTTHS": "Bộ Luật Tố Tụng Hình Sự",
    "BLTTDS": "Bộ Luật Tố Tụng Dân Sự",
    "BLHS2015": "Bộ Luật Hình Sự năm 2015",
    "BLDS2015": "Bộ Luật Dân Sự năm 2015",
    "BLDS2005": "Bộ Luật Dân Sự năm 2005",
    "BLHS1999": "Bộ Luật Hình Sự năm 1999",
    "BLHS2009": "Bộ Luật Hình Sự năm 2009",
    "BLTTDS2004": "Bộ Luật Tố Tụng Dân Sự năm 2004",
    "BLTTHS2003": "Bộ Luật Tố Tụng Hình Sự năm 2003",
    
    # Labor and Employment
    "BLLĐ": "Bộ Luật Lao Động",
    "BLLD": "Bộ Luật Lao Động",
    "BLLĐ2019": "Bộ Luật Lao Động năm 2019",
    "BLLĐ2012": "Bộ Luật Lao Động năm 2012",
    
    # Commercial and Business
    "BLTM": "Bộ Luật Thương Mại",
    "BLTM2005": "Bộ Luật Thương Mại năm 2005",
    "LDT": "Luật Doanh Nghiệp",
    "LDN": "Luật Doanh Nghiệp",
    "LDN2020": "Luật Doanh Nghiệp năm 2020",
    "LDN2014": "Luật Doanh Nghiệp năm 2014",
    "LDN2005": "Luật Doanh Nghiệp năm 2005",
    "LĐT": "Luận Đầu Tư",
    "LĐT2020": "Luật Đầu Tư năm 2020",
    "LĐT2014": "Luật Đầu Tư năm 2014",
    
    # Marriage, Family, and Civil
    "LHN": "Luật Hôn Nhân",
    "LHN&GĐ": "Luật Hôn Nhân và Gia Đình",
    "LHN2014": "Luật Hôn Nhân và Gia Đình năm 2014",
    
    # Land and Real Estate
    "LĐĐ": "Luật Đất Đai",
    "LĐĐ2013": "Luật Đất Đai năm 2013",
    "LĐĐ2003": "Luật Đất Đai năm 2003",
    "LN": "Luật Nhà ở",
    "LN2014": "Luật Nhà ở năm 2014",
    "LN2005": "Luật Nhà ở năm 2005",
    
    # Tax and Finance
    "LGTGT": "Luật Giá Trị Gia Tăng",
    "LTNCN": "Luật Thuế Thu Nhập Cá Nhân",
    "LTNCN2007": "Luật Thuế Thu Nhập Cá Nhân năm 2007",
    "LTNTDN": "Luật Thuế Thu Nhập Doanh Nghiệp",
    "LTNTDN2008": "Luật Thuế Thu Nhập Doanh Nghiệp năm 2008",
    
    # Intellectual Property
    "LSHTT": "Luật Sở Hữu Trí Tuệ",
    "LSHTT2005": "Luật Sở Hữu Trí Tuệ năm 2005",
    
    # Competition and Consumer
    "LCT": "Luật Cạnh Tranh",
    "LCT2018": "Luật Cạnh Tranh năm 2018",
    "LCT2004": "Luật Cạnh Tranh năm 2004",
    "LBVNTD": "Luật Bảo Vệ NgườI Tiêu Dùng",
    
    # Government Decrees
    "NĐ-CP": "Nghị Định Chính Phủ",
    "NĐ": "Nghị Định",
    "CP": "Chính Phủ",
    
    # Circulars
    "TT-BLĐTBXH": "Thông Tư Bộ Lao Động Thương Binh và Xã Hội",
    "TT-BTC": "Thông Tư Bộ Tài Chính",
    "TT-BTP": "Thông Tư Bộ Tư Pháp",
    "TT-BTNMT": "Thông Tư Bộ Tài Nguyên và Môi Trường",
    "TT-BXD": "Thông Tư Bộ Xây Dựng",
    "TT-BCT": "Thông Tư Bộ Công Thương",
    "TT-BYT": "Thông Tư Bộ Y Tế",
    "TT-BGDĐT": "Thông Tư Bộ Giáo Dục và Đào Tạo",
    "TT-BTTTT": "Thông Tư Bộ Thông Tin và Truyền Thông",
    "TT-BQP": "Thông Tư Bộ Quốc Phòng",
    "TT-BNV": "Thông Tư Bộ Nội Vụ",
    "TT-BKHCN": "Thông Tư Bộ Khoa Học và Công Nghệ",
    "TT-BKHĐT": "Thông Tư Bộ Kế Hoạch và Đầu Tư",
    "TT-BGTVT": "Thông Tư Bộ Giao Thông Vận Tải",
    "TT-BNNPTNT": "Thông Tư Bộ Nông Nghiệp và Phát Triển Nông Thôn",
    "TT-BVHTTDL": "Thông Tư Bộ Văn Hóa Thể Thao và Du Lịch",
    "TT": "Thông Tư",
    
    # Other Legal Documents
    "QĐ": "Quyết Định",
    "NQ": "Nghị Quyết",
    "TB": "Thông Báo",
    "CV": "Công Văn",
    "CT": "Chỉ Thị",
    "KL": "Kết Luận",
    "TTg": "Thủ Tướng Chính Phủ",
    "UBND": "Ủy Ban Nhân Dân",
    "HĐND": "Hội Đồng Nhân Dân",
    "QH": "Quốc Hội",
    "TAND": "Tòa Án Nhân Dân",
    "VKSND": "Viện Kiểm Sát Nhân Dân",
    "ST": "Sơ Thẩm",
    "PT": "Phúc Thẩm",
    "TT": "Tái Thẩm",
    "GQ": "Giám Đốc Thẩm",
}

LEGAL_SYNONYMS: dict[str, list[str]] = {
    # Business entities
    "công_ty": ["doanh_nghiệp", "tổ_chức_kinh_tế", "công_ty", "doanh_nghiệp_tư_nhân", "hợp_danh", "cổ_phần"],
    "doanh_nghiệp": ["công_ty", "tổ_chức_kinh_tế", "doanh_nghiệp"],
    "tổ_chức_kinh_tế": ["công_ty", "doanh_nghiệp", "tổ_chức_kinh_tế"],
    
    # Employees/Workers
    "nhân_viên": ["ngườI_lao_động", "công_nhân", "ngườI_làm_công", "nhân_viên", "ngườI_được_tuyển_dụng"],
    "ngườI_lao_động": ["nhân_viên", "công_nhân", "ngườI_làm_công", "ngườI_lao_động"],
    "công_nhân": ["nhân_viên", "ngườI_lao_động", "công_nhân"],
    
    # Insurance
    "bảo_hiểm": ["bảo_hiểm_xã_hội", "bảo_hiểm_y_tế", "bảo_hiểm_thất_nghiệp", "bảo_hiểm"],
    "bảo_hiểm_xã_hội": ["bảo_hiểm", "bhxh", "bảo_hiểm_xã_hội"],
    "bhxh": ["bảo_hiểm_xã_hội", "bảo_hiểm"],
    
    # Negation/Prohibition
    "không_được": ["cấm", "nghiêm_cấm", "không_được_phép", "không_cho_phép", "không_có_quyền", "không_được"],
    "cấm": ["không_được", "nghiêm_cấm", "không_được_phép", "không_cho_phép", "cấm"],
    "nghiêm_cấm": ["cấm", "không_được", "không_được_phép", "nghiêm_cấm"],
    "không_được_phép": ["không_được", "cấm", "nghiêm_cấm", "không_được_phép"],
    
    # Contracts/Agreements
    "hợp_đồng": ["giao_kết", "thỏa_thuận", "cam_kết", "hợp_đồng", "hợp_đồng_lao_động"],
    "giao_kết": ["hợp_đồng", "thỏa_thuận", "giao_kết"],
    "thỏa_thuận": ["hợp_đồng", "giao_kết", "thỏa_thuận", "cam_kết"],
    
    # Violations
    "vi_phạm": ["xâm_phạm", "trái_quy_định", "không_tuân_thủ", "vi_phạm", "phạm_tội"],
    "xâm_phạm": ["vi_phạm", "trái_quy_định", "xâm_phạm"],
    "trái_quy_định": ["vi_phạm", "xâm_phạm", "trái_quy_định", "không_tuân_thủ"],
    
    # Compensation
    "bồi_thường": ["đền_bù", "bồi_thường_thiệt_hại", "bồi_thường"],
    "đền_bù": ["bồi_thường", "đền_bù", "bồi_thường_thiệt_hại"],
    
    # Termination
    "chấm_dứt": ["hủy_bỏ", "thanh_lý", "đơn_phương_chấm_dứt", "chấm_dứt", "chấm_dứt_hợp_đồng"],
    "hủy_bỏ": ["chấm_dứt", "thanh_lý", "hủy_bỏ", "vô_hiệu"],
    "thanh_lý": ["chấm_dứt", "hủy_bỏ", "thanh_lý", "giải_quyết_hậu_quả"],
    
    # Rights and Obligations
    "quyền": ["quyền_lợi", "lợi_ích", "quyền_hạn", "quyền"],
    "nghĩa_vụ": ["trách_nhiệm", "bổn_phận", "nghĩa_vụ"],
    "trách_nhiệm": ["nghĩa_vụ", "bổn_phận", "trách_nhiệm"],
    
    # Legal terms
    "điều_khoản": ["khoản", "điểm", "điều_luật", "điều_khoản"],
    "khoản": ["điều_khoản", "điểm", "khoản"],
    "điểm": ["khoản", "điều_khoản", "điểm"],
    
    # Parties
    "bên": ["bên_A", "bên_B", "các_bên", "đối_tác", "bên"],
    "các_bên": ["bên", "đối_tác", "các_bên"],
    
    # Time periods
    "thờI_hạn": ["kỳ_hạn", "thờI_gian", "hạn", "thờI_hạn"],
    "kỳ_hạn": ["thờI_hạn", "thờI_gian", "kỳ_hạn"],
    
    # Salary/Wages
    "lương": ["tiền_lương", "tiền_công", "thù_lao", "lương"],
    "tiền_lương": ["lương", "tiền_công", "tiền_lương"],
    
    # Working time
    "giờ_làm_việc": ["thờI_gian_làm_việc", "ca_làm_việc", "giờ_làm_việc"],
    "thờI_gian_làm_việc": ["giờ_làm_việc", "ca_làm_việc", "thờI_gian_làm_việc"],
    
    # Leave
    "nghỉ_phép": ["nghỉ_hằng_năm", "nghỉ_có_lương", "nghỉ_phép_năm", "nghỉ_phép"],
    "nghỉ_hằng_năm": ["nghỉ_phép", "nghỉ_phép_năm", "nghỉ_hằng_năm"],
}

# Verb form patterns for Vietnamese legal texts
# Maps base verbs to their common derivational/nominalized forms
VERB_FORM_PATTERNS: dict[str, list[str]] = {
    "quản lý": ["được quản lý", "việc quản lý", "công tác quản lý"],
    "thành lập": ["được thành lập", "việc thành lập"],
    "cung cấp": ["được cung cấp", "việc cung cấp"],
    "quy định": ["được quy định", "theo quy định", "các quy định"],
    "báo cáo": ["việc báo cáo", "chế độ báo cáo"],
    "thanh toán": ["việc thanh toán", "được thanh toán"],
    "sử dụng": ["được sử dụng", "việc sử dụng", "quyền sử dụng"],
    "bảo vệ": ["được bảo vệ", "việc bảo vệ", "công tác bảo vệ"],
    "kiểm tra": ["được kiểm tra", "việc kiểm tra", "công tác kiểm tra"],
    "giám sát": ["được giám sát", "việc giám sát", "công tác giám sát"],
    "xử lý": ["được xử lý", "việc xử lý"],
    "phê duyệt": ["được phê duyệt", "việc phê duyệt"],
    "cấp phép": ["được cấp phép", "việc cấp phép", "giấy phép"],
    "đăng ký": ["được đăng ký", "việc đăng ký", "thủ tục đăng ký"],
    "thu phí": ["việc thu phí", "mức thu phí"],
    "giao đất": ["được giao đất", "việc giao đất"],
    "trồng rừng": ["việc trồng rừng", "công tác trồng rừng"],
}

# Legal concept clusters for domain expansion
# Maps broad legal categories to related specific terms
LEGAL_CONCEPT_CLUSTERS: dict[str, list[str]] = {
    "phí dịch vụ": ["giá dịch vụ", "lệ phí", "phí bến bãi", "mức phí", "biểu phí"],
    "giá cả": ["giá dịch vụ", "niêm yết giá", "quy định giá", "mức giá"],
    "đất đai": ["đất lâm nghiệp", "đất nông nghiệp", "quyền sử dụng đất", "quản lý đất"],
    "tài nguyên": ["tài nguyên thiên nhiên", "môi trường", "khoáng sản", "rừng"],
    "tổ chức bộ máy": ["cơ cấu tổ chức", "bộ máy hành chính", "phân cấp quản lý", "nhân sự"],
    "ban quản lý": ["ban quản lý dự án", "ban điều hành", "hội đồng quản lý"],
    "thủ tục hành chính": ["thủ tục hành chính công", "giấy phép", "đăng ký", "cấp phép"],
    "báo cáo": ["báo cáo định kỳ", "chế độ báo cáo", "báo cáo tài chính"],
    "hợp đồng": ["giao kết hợp đồng", "thực hiện hợp đồng", "điều khoản hợp đồng"],
    "xử phạt": ["xử phạt vi phạm", "xử phạt hành chính", "chế tài"],
    "môi trường": ["bảo vệ môi trường", "phục hồi môi trường", "ký quỹ môi trường", "ô nhiễm"],
    "ngân sách": ["ngân sách nhà nước", "thu chi ngân sách", "tài chính công"],
    "đầu tư": ["dự án đầu tư", "vốn đầu tư", "quản lý đầu tư"],
    "giữ xe": ["dịch vụ giữ xe", "phí giữ xe", "bến bãi", "trông giữ xe"],
    "niêm yết": ["niêm yết giá", "niêm yết công khai", "công bố"],
    "phục hồi": ["phục hồi môi trường", "ký quỹ phục hồi", "cải tạo phục hồi"],
    "lâm nghiệp": ["đất lâm nghiệp", "rừng", "trồng rừng", "quản lý rừng"],
}

# Negation patterns (Vietnamese)
NEGATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Strong negation/prohibition
    (re.compile(r'\bkhông\s+được\s+phép\b', re.IGNORECASE), "không được phép"),
    (re.compile(r'\bkhông\s+được\b', re.IGNORECASE), "không được"),
    (re.compile(r'\bnghiêm\s+cấm\b', re.IGNORECASE), "nghiêm cấm"),
    (re.compile(r'\bcấm\b', re.IGNORECASE), "cấm"),
    (re.compile(r'\bkhông\s+cho\s+phép\b', re.IGNORECASE), "không cho phép"),
    (re.compile(r'\bkhông\s+có\s+quyền\b', re.IGNORECASE), "không có quyền"),
    (re.compile(r'\bkhông\s+thể\b', re.IGNORECASE), "không thể"),
    (re.compile(r'\bkhông\s+được\s+quyền\b', re.IGNORECASE), "không được quyền"),
    
    # Moderate negation
    (re.compile(r'\bkhông\s+nên\b', re.IGNORECASE), "không nên"),
    (re.compile(r'\bkhông\s+được\s+phép\s+để\b', re.IGNORECASE), "không được phép để"),
    
    # Contractual negation
    (re.compile(r'\bkhông\s+bao\s+gồm\b', re.IGNORECASE), "không bao gồm"),
    (re.compile(r'\bkhông\s+áp\s+dụng\b', re.IGNORECASE), "không áp dụng"),
    (re.compile(r'\bkhông\s+có\s+hiệu\s+lực\b', re.IGNORECASE), "không có hiệu lực"),
    (re.compile(r'\bvô\s+hiệu\b', re.IGNORECASE), "vô hiệu"),
]

# Citation patterns (compiled regex)
CITATION_PATTERNS: dict[str, re.Pattern] = {
    "article": re.compile(r'Điều\s+(\d+[a-zA-Z]?(?:\.\d+)?)', re.IGNORECASE | re.UNICODE),
    "law_year": re.compile(r'Luật\s+(.+?)\s+năm\s+(\d{4})', re.IGNORECASE | re.UNICODE),
    "decree": re.compile(r'Nghị\s+định\s+(\d+/\d{4}/NĐ-CP)', re.IGNORECASE | re.UNICODE),
    "circular": re.compile(r'Thông\s+tư\s+(\d+/\d{4}/TT-\w+)', re.IGNORECASE | re.UNICODE),
    "subsection": re.compile(r'Khoản\s+(\d+[a-zA-Z]?(?:\.\d+)?)', re.IGNORECASE | re.UNICODE),
    "point": re.compile(r'[Đđ]iểm\s+([a-zA-Z]\d?)', re.IGNORECASE | re.UNICODE),
    "chapter": re.compile(r'Chương\s+(\d+|[IVX]+)', re.IGNORECASE | re.UNICODE),
    "section": re.compile(r'Mục\s+(\d+|[IVX]+)', re.IGNORECASE | re.UNICODE),
}


# =============================================================================
# LEGAL QUERY PLANNER
# =============================================================================

class LegalQueryPlanner:
    """
    Transforms raw user queries into structured QueryPlan objects.
    Target latency: 30-50ms per query.
    
    Pipeline: normalize -> expand abbreviations -> expand synonyms -> detect negation -> extract citations -> classify strategy
    """
    
    def __init__(self) -> None:
        """Initialize the query planner with compiled patterns."""
        self._abbreviation_patterns: dict[re.Pattern, str] = {}
        self._compile_abbreviation_patterns()
    
    def _compile_abbreviation_patterns(self) -> None:
        """Compile abbreviation patterns for efficient matching."""
        for abbrev, expansion in LEGAL_ABBREVIATIONS.items():
            # Word boundary aware pattern
            pattern = re.compile(r'\b' + re.escape(abbrev) + r'\b', re.IGNORECASE)
            self._abbreviation_patterns[pattern] = expansion
    
    def plan(self, raw_query: str) -> QueryPlan:
        """
        Main entry point for query planning.
        
        Pipeline:
        1. Normalize text (unicode, whitespace, diacritics heuristic)
        2. Expand abbreviations
        3. Expand legal synonyms
        4. Detect negation + extract scope
        5. Extract citation patterns
        6. Classify query strategy
        7. Build and return QueryPlan
        
        Args:
            raw_query: The raw user query string
            
        Returns:
            QueryPlan: Structured query plan with all metadata
        """
        # Step 1: Normalize
        normalized = self.normalize_query(raw_query)
        
        # Step 2: Expand abbreviations
        expanded = self.expand_abbreviations(normalized)
        
        # Step 3: Expand synonyms
        expansion_variants = self.expand_synonyms(expanded)
        
        # Step 4: Detect negation
        has_negation, negation_scope = self.detect_negation(expanded)
        
        # Step 5: Extract citations
        citations = self.extract_citations(expanded)
        
        # Step 6: Classify strategy
        strategy = self.classify_strategy(has_negation, citations)
        
        # Step 7: Build QueryPlan
        return QueryPlan(
            original_query=raw_query,
            normalized_query=normalized,
            expansion_variants=expansion_variants,
            has_negation=has_negation,
            negation_scope=negation_scope,
            citations=citations,
            strategy=strategy,
            search_filters={}
        )
    
    def normalize_query(self, text: str) -> str:
        """
        Normalize query text for consistent processing.
        
        Steps:
        - Unicode NFC normalization
        - Whitespace normalization
        - Lowercase for matching (original preserved in QueryPlan)
        
        Args:
            text: Raw input text
            
        Returns:
            Normalized text string
        """
        # Unicode NFC normalization
        normalized = unicodedata.normalize('NFC', text)
        
        # Whitespace normalization: collapse multiple spaces/newlines
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        # Lowercase for consistent matching
        normalized = normalized.lower()
        
        return normalized
    
    def expand_abbreviations(self, text: str) -> str:
        """
        Expand legal abbreviations to their full forms.
        
        Uses comprehensive dictionary of Vietnamese legal abbreviations.
        Case-insensitive matching with word boundary awareness.
        
        Args:
            text: Normalized input text
            
        Returns:
            Text with abbreviations expanded
        """
        result = text
        
        # Sort patterns by length (longest first) to avoid partial matches
        sorted_patterns = sorted(
            self._abbreviation_patterns.items(),
            key=lambda x: len(LEGAL_ABBREVIATIONS.get(x[1], '')),
            reverse=True
        )
        
        for pattern, expansion in sorted_patterns:
            result = pattern.sub(expansion, result)
        
        return result
    
    def expand_synonyms(self, text: str) -> list[str]:
        """
        Expand legal synonyms, verb forms, and concept clusters to create query variants.
        
        Uses Vietnamese legal synonym dictionary, verb form patterns, and concept
        clusters to generate semantically equivalent query variations for better retrieval.
        
        Args:
            text: Input text (after abbreviation expansion)
            
        Returns:
            List of expanded query variants including original (capped at ~10 variants)
        """
        variants: set[str] = {text}
        
        # Step 1: Expand synonyms (existing logic)
        for term, synonyms in LEGAL_SYNONYMS.items():
            # Check if term appears in text (as word or with underscores)
            term_pattern = term.replace('_', r'\s+')
            if re.search(r'\b' + term_pattern + r'\b', text, re.IGNORECASE):
                # Generate variants by replacing with each synonym
                for synonym in synonyms:
                    if synonym != term:
                        synonym_text = synonym.replace('_', ' ')
                        term_text = term.replace('_', ' ')
                        # Replace all occurrences
                        variant = re.sub(
                            r'\b' + re.escape(term_text) + r'\b',
                            synonym_text,
                            text,
                            flags=re.IGNORECASE
                        )
                        variants.add(variant)
        
        
        # Step 2: Expand verb forms
        # Vietnamese legal texts use different verb forms for the same concept
        for verb, forms in VERB_FORM_PATTERNS.items():
            if verb in text:
                # Add each verb form variant
                for form in forms:
                    if form != verb:
                        variant = text.replace(verb, form)
                        variants.add(variant)
        
        
        # Step 3: Expand legal concept clusters
        # Map broad legal categories to related specific terms
        for concept, related_terms in LEGAL_CONCEPT_CLUSTERS.items():
            if concept in text:
                # Add each related term as a variant
                for related in related_terms:
                    if related != concept:
                        variant = text.replace(concept, related)
                        variants.add(variant)
        
        
        # Step 4: De-duplicate and cap total variants
        # The caller (hybrid.py) will further limit to config.search_expansion_max_variants
        # We cap here to prevent explosion before the caller's cap
        MAX_VARIANTS = 10
        unique_variants = list(variants)
        
        # Always keep the original text first
        if text in unique_variants:
            unique_variants.remove(text)
            unique_variants.insert(0, text)
        
        
        return unique_variants[:MAX_VARIANTS]
    
    def detect_negation(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Detect negation patterns and extract negation scope.
        
        Patterns include: không, không được, cấm, nghiêm cấm, etc.
        Extracts what is being negated (negation scope).
        
        Args:
            text: Input text to analyze
            
        Returns:
            Tuple of (has_negation, negation_scope)
            - has_negation: True if negation detected
            - negation_scope: The text being negated, or None
        """
        has_negation = False
        negation_scope: Optional[str] = None
        
        for pattern, negation_type in NEGATION_PATTERNS:
            match = pattern.search(text)
            if match:
                has_negation = True
                # Extract scope: text after the negation pattern
                scope_start = match.end()
                # Get up to next punctuation or reasonable boundary
                scope_text = text[scope_start:].strip()
                # Limit scope to first sentence or clause
                scope_match = re.match(r'^([^,.;!?]+)', scope_text)
                if scope_match:
                    negation_scope = scope_match.group(1).strip()
                else:
                    negation_scope = scope_text[:100]  # Limit length
                break
        
        return has_negation, negation_scope
    
    def extract_citations(self, text: str) -> list[str]:
        """
        Extract legal citation patterns from text.
        
        Patterns:
        - Điều (\d+) -- Article references
        - Luật (.+?) năm (\d{4}) -- Law + year
        - Nghị định (\d+/\d{4}/NĐ-CP) -- Decree numbers
        - Thông tư (\d+/\d{4}/TT-\w+) -- Circular numbers
        - Khoản (\d+) -- Subsection references
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of extracted citation strings
        """
        citations: list[str] = []
        
        # Extract articles
        for match in CITATION_PATTERNS["article"].finditer(text):
            citations.append(f"Điều {match.group(1)}")
        
        # Extract laws with years
        for match in CITATION_PATTERNS["law_year"].finditer(text):
            law_name = match.group(1).strip()
            year = match.group(2)
            citations.append(f"Luật {law_name} năm {year}")
        
        # Extract decrees
        for match in CITATION_PATTERNS["decree"].finditer(text):
            citations.append(f"Nghị định {match.group(1)}")
        
        # Extract circulars
        for match in CITATION_PATTERNS["circular"].finditer(text):
            citations.append(f"Thông tư {match.group(1)}")
        
        # Extract subsections
        for match in CITATION_PATTERNS["subsection"].finditer(text):
            citations.append(f"Khoản {match.group(1)}")
        
        # Extract points
        for match in CITATION_PATTERNS["point"].finditer(text):
            citations.append(f"Điểm {match.group(1)}")
        
        # Extract chapters
        for match in CITATION_PATTERNS["chapter"].finditer(text):
            citations.append(f"Chương {match.group(1)}")
        
        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_citations: list[str] = []
        for citation in citations:
            if citation not in seen:
                seen.add(citation)
                unique_citations.append(citation)
        
        return unique_citations
    
    def classify_strategy(self, has_negation: bool, citations: list[str]) -> QueryStrategy:
        """
        Classify the query strategy based on detected features.
        
        Strategy selection:
        - CITATION: If citations found -> exact legal reference lookup
        - NEGATION: If negation detected -> negation-aware retrieval
        - SEMANTIC: Default -> standard hybrid retrieval
        
        Args:
            has_negation: Whether negation was detected
            citations: List of extracted citations
            
        Returns:
            QueryStrategy enum value
        """
        if citations:
            return QueryStrategy.CITATION
        elif has_negation:
            return QueryStrategy.NEGATION
        else:
            return QueryStrategy.SEMANTIC


# Legacy alias for backward compatibility
QueryPlanner = LegalQueryPlanner
