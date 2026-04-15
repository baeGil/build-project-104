"""Vietnamese Text Normalizer for Legal Documents.

This module provides text normalization specific to Vietnamese legal text,
including Unicode normalization, diacritic handling, abbreviation expansion,
and legal term standardization.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Pattern


# Comprehensive dictionary of Vietnamese legal abbreviations
LEGAL_ABBREVIATIONS: dict[str, str] = {
    # Core legal codes
    "BLHS": "Bộ Luật Hình Sự",
    "BLDS": "Bộ Luật Dân Sự",
    "BLTTHS": "Bộ Luật Tố Tụng Hình Sự",
    "BLTTDS": "Bộ Luật Tố Tụng Dân Sự",
    "BLHS": "Bộ Luật Hình Sự",
    "BLLĐ": "Bộ Luật Lao Động",
    "BLDS": "Bộ Luật Dân Sự",
    # Decrees
    "NĐ-CP": "Nghị định Chính phủ",
    "NĐ": "Nghị định",
    "NĐCP": "Nghị định Chính phủ",
    # Circulars
    "TT": "Thông tư",
    "TT-BTC": "Thông tư Bộ Tài chính",
    "TT-BTP": "Thông tư Bộ Tư pháp",
    "TT-BCT": "Thông tư Bộ Công thương",
    "TT-BLĐTBXH": "Thông tư Bộ Lao động Thương binh và Xã hội",
    "TT-NHNN": "Thông tư Ngân hàng Nhà nước",
    "TT-BGDĐT": "Thông tư Bộ Giáo dục và Đào tạo",
    "TT-BYT": "Thông tư Bộ Y tế",
    "TT-BXD": "Thông tư Bộ Xây dựng",
    "TT-BTNMT": "Thông tư Bộ Tài nguyên và Môi trường",
    "TT-BTTTT": "Thông tư Bộ Thông tin và Truyền thông",
    "TT-BQP": "Thông tư Bộ Quốc phòng",
    "TT-BNG": "Thông tư Bộ Ngoại giao",
    "TT-BCA": "Thông tư Bộ Công an",
    "TT-BNNPTNT": "Thông tư Bộ Nông nghiệp và Phát triển nông thôn",
    # Decisions
    "QĐ": "Quyết định",
    "QĐ-TTg": "Quyết định Thủ tướng Chính phủ",
    "QĐ-UBND": "Quyết định Ủy ban nhân dân",
    # Resolutions
    "NQ": "Nghị quyết",
    "NQ-TVQH": "Nghị quyết Thường vụ Quốc hội",
    "NQ-CP": "Nghị quyết Chính phủ",
    # Laws
    "LĐ": "Luật",
    "PL": "Pháp lệnh",
    "Hiến pháp": "Hiến pháp",
    "HP": "Hiến pháp",
    # Government bodies
    "CP": "Chính phủ",
    "QH": "Quốc hội",
    "TVQH": "Thường vụ Quốc hội",
    "UBTVQH": "Ủy ban Thường vụ Quốc hội",
    "TTg": "Thủ tướng",
    "TTG": "Thủ tướng Chính phủ",
    "BTC": "Bộ Tài chính",
    "BTP": "Bộ Tư pháp",
    "BCT": "Bộ Công thương",
    "BLĐTBXH": "Bộ Lao động Thương binh và Xã hội",
    "NHNN": "Ngân hàng Nhà nước",
    "BGDĐT": "Bộ Giáo dục và Đào tạo",
    "BYT": "Bộ Y tế",
    "BXD": "Bộ Xây dựng",
    "BTNMT": "Bộ Tài nguyên và Môi trường",
    "BTTTT": "Bộ Thông tin và Truyền thông",
    "BQP": "Bộ Quốc phòng",
    "BNG": "Bộ Ngoại giao",
    "BCA": "Bộ Công an",
    "BNNPTNT": "Bộ Nông nghiệp và Phát triển nông thôn",
    "UBND": "Ủy ban nhân dân",
    # Legal terms
    "HS": "Hình sự",
    "DS": "Dân sự",
    "HC": "Hành chính",
    "HĐ": "Hợp đồng",
    "HĐLĐ": "Hợp đồng lao động",
    "HĐMB": "Hợp đồng mua bán",
    "HĐDV": "Hợp đồng dịch vụ",
    "KCN": "Khu công nghiệp",
    "KCX": "Khu chế xuất",
    "DN": "Doanh nghiệp",
    "DNNN": "Doanh nghiệp nhà nước",
    "DNTN": "Doanh nghiệp tư nhân",
    "TNHH": "Trách nhiệm hữu hạn",
    "CĐ": "Công đoàn",
    "CĐDC": "Công đoàn độc lập",
    "NLĐ": "NgườI lao động",
    "NSDLĐ": "NgườI sử dụng lao động",
    "BHXH": "Bảo hiểm xã hội",
    "BHYT": "Bảo hiểm y tế",
    "BHTN": "Bảo hiểm thất nghiệp",
    "TNCN": "Thu nhập cá nhân",
    "GTGT": "Giá trị gia tăng",
    "TNDN": "Thu nhập doanh nghiệp",
    "XK": "Xuất khẩu",
    "NK": "Nhập khẩu",
    "XNK": "Xuất nhập khẩu",
    "TM": "Thương mại",
    "ĐT": "Đầu tư",
    "ĐKKD": "Đăng ký kinh doanh",
    "GPKD": "Giấy phép kinh doanh",
    "CMND": "Chứng minh nhân dân",
    "CCCD": "Căn cước công dân",
    "TTHC": "Thủ tục hành chính",
    "VP": "Vi phạm",
    "XPHC": "Xử phạt hành chính",
    "HSVPHC": "Hành vi vi phạm hành chính",
}

# Common Vietnamese words with diacritics for detection
VIETNAMESE_DIACRITIC_WORDS: list[str] = [
    "ngày", "tháng", "năm", "điều", "khoản", "điểm", "luật", "nghị", "định",
    "thông", "tư", "quyết", "định", "bộ", "pháp", "hình", "sự", "dân",
    "chính", "phủ", "quốc", "hội", "thành", "phố", "tỉnh", "huyện",
    "công", "ty", "trách", "nhiệm", "hữu", "hạn", "cổ", "phần",
    "hợp", "đồng", "lao", "động", "thương", "mại", "dịch", "vụ",
    "bảo", "hiểm", "xã", "hội", "y", "tế", "giáo", "dục",
]

# Date format patterns for normalization
DATE_PATTERNS: list[tuple[Pattern[str], str]] = [
    # "ngày 12 tháng 4 năm 2026" -> "2026-04-12"
    (
        re.compile(
            r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            re.IGNORECASE | re.UNICODE,
        ),
        r"\3-\2-\1",
    ),
    # "12/4/2026" or "12-4-2026" -> "2026-04-12"
    (
        re.compile(
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
            re.UNICODE,
        ),
        r"\3-\2-\1",
    ),
    # "2026/4/12" -> "2026-04-12"
    (
        re.compile(
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
            re.UNICODE,
        ),
        r"\1-\2-\3",
    ),
]


def normalize_unicode(text: str) -> str:
    """Normalize Unicode text to NFC form.

    NFC (Normalization Form C) composes characters and diacritics into
    single codepoints where possible, ensuring consistent representation.

    Args:
        text: Raw text to normalize.

    Returns:
        NFC-normalized text.
    """
    return unicodedata.normalize("NFC", text)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Collapses multiple spaces, tabs into single spaces,
    normalizes line breaks, and strips leading/trailing whitespace.

    Args:
        text: Raw text to normalize.

    Returns:
        Whitespace-normalized text.
    """
    # Replace tabs with spaces
    text = text.replace("\t", " ")
    # Collapse multiple spaces
    text = re.sub(r" +", " ", text)
    # Normalize line breaks (handle \r\n and \r)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple line breaks to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def expand_abbreviations(text: str, custom_dict: dict[str, str] | None = None) -> str:
    """Expand legal abbreviations in text.

    Expands common Vietnamese legal abbreviations to their full forms.
    Custom abbreviations can be provided to override or extend defaults.

    Args:
        text: Text containing abbreviations.
        custom_dict: Optional dictionary of custom abbreviations.

    Returns:
        Text with abbreviations expanded.
    """
    # Merge custom dict with default
    abbrev_dict = LEGAL_ABBREVIATIONS.copy()
    if custom_dict:
        abbrev_dict.update(custom_dict)

    # Sort by length (longest first) to avoid partial replacements
    sorted_abbrs = sorted(abbrev_dict.items(), key=lambda x: len(x[0]), reverse=True)

    result = text
    for abbr, full_form in sorted_abbrs:
        # Match abbreviation as whole word, case-insensitive
        pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE)
        result = pattern.sub(full_form, result)

    return result


def detect_missing_diacritics(text: str) -> bool:
    """Heuristic to detect if text is missing Vietnamese diacritics.

    Checks if common Vietnamese words appear without their expected diacritics.

    Args:
        text: Text to analyze.

    Returns:
        True if text appears to be missing diacritics, False otherwise.
    """
    # Sample of text (first 2000 chars for efficiency)
    sample = text[:2000].lower()

    # Count words that should have diacritics but don't
    missing_count = 0
    total_check_words = 0

    for word in VIETNAMESE_DIACRITIC_WORDS:
        # Check for the word without diacritics
        undiacritized = unicodedata.normalize("NFD", word)
        undiacritized = "".join(c for c in undiacritized if unicodedata.category(c) != "Mn")

        # Use word boundary matching to avoid matching substrings
        if re.search(r'\b' + re.escape(undiacritized) + r'\b', sample):
            total_check_words += 1
            # If we see the undiacritized version but not the proper one
            if word not in sample:
                missing_count += 1

    # If more than 50% of check words are missing diacritics, flag it
    if total_check_words > 0:
        ratio = missing_count / total_check_words
        return ratio > 0.5

    return False


def normalize_date_format(text: str) -> str:
    """Standardize date formats to ISO format (YYYY-MM-DD).

    Converts various Vietnamese date formats to ISO 8601 format.

    Args:
        text: Text containing dates.

    Returns:
        Text with standardized date formats.
    """
    result = text
    for pattern, replacement in DATE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def normalize_legal_text(text: str) -> str:
    """Full normalization pipeline for Vietnamese legal text.

    Applies the complete normalization pipeline:
    1. Unicode NFC normalization
    2. Whitespace normalization
    3. Abbreviation expansion

    Args:
        text: Raw legal text.

    Returns:
        Fully normalized text.
    """
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    text = expand_abbreviations(text)
    return text


class TextNormalizer:
    """Normalizer for Vietnamese legal text.

    Performs the following normalizations:
    - Unicode NFC normalization
    - Diacritic standardization
    - Legal term normalization
    - Whitespace and punctuation cleanup
    - Case standardization for legal references
    """

    def __init__(self, custom_abbreviations: dict[str, str] | None = None) -> None:
        """Initialize the text normalizer.

        Args:
            custom_abbreviations: Optional custom abbreviation dictionary.
        """
        self.custom_abbreviations = custom_abbreviations or {}

    def normalize(self, text: str) -> str:
        """Normalize Vietnamese legal text.

        Args:
            text: Raw text to normalize.

        Returns:
            Normalized text.
        """
        return normalize_legal_text(text)

    def normalize_citation(self, citation: str) -> str:
        """Normalize a legal citation to standard format.

        Args:
            citation: Raw citation text.

        Returns:
            Normalized citation.
        """
        text = normalize_unicode(citation)
        text = normalize_whitespace(text)
        # Expand abbreviations in citation
        text = expand_abbreviations(text, self.custom_abbreviations)
        # Standardize case for document types and "Điều"
        text = re.sub(
            r"\b(luật|nghị\s+định|thông\s+tư|quyết\s+định)\b",
            lambda m: m.group(0).title(),
            text,
            flags=re.IGNORECASE | re.UNICODE,
        )
        # Capitalize "Điều" at the beginning of the citation
        text = re.sub(
            r"^điều\b",
            "Điều",
            text,
            flags=re.IGNORECASE | re.UNICODE,
        )
        return text.strip()

    def detect_diacritics_missing(self, text: str) -> bool:
        """Check if text appears to be missing Vietnamese diacritics.

        Args:
            text: Text to analyze.

        Returns:
            True if diacritics appear to be missing.
        """
        return detect_missing_diacritics(text)
