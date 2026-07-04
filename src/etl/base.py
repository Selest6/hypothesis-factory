from __future__ import annotations

import re
from pathlib import Path

CASE_FOLDER_MAP = {
    "пример 1": ("kgmk", "КГМК"),
    "пример 2": ("nof_vkr", "НОФ вкр"),
    "пример 3": ("nof_med", "НОФ мед"),
    "пример 4": ("tof", "ТОФ"),
}

CASE_NAME_PATTERNS: list[tuple[str, str, str]] = [
    ("kgmk", "КГМК", "кгмк"),
    ("nof_med", "НОФ мед", "ноф мед"),
    ("nof_vkr", "НОФ вкр", "ноф вкр"),
    ("tof", "ТОФ", "тоф"),
]

MINERAL_NAMES = {
    "раскрытый pnt/cp",
    "закрытый pnt/cp",
    "примесь в пирротине",
    "силикатная форма/валлериит",
    "силикатная форма/валлерiит",
    "пирит/другие элемент 29 сульфиды",
    "мillerit",
    "миллерит",
    "потери (расписать)",
    "свободный слот",
    "извлекаемый металл",
    "не извлекаемый металл",
}

SIZE_CLASS_RE = re.compile(
    r"(\+|\-)?\s*\d+\s*(\+\s*\d+)?\s*мкм|класс крупности",
    re.IGNORECASE,
)

# Organizer meta-doc: how to read Excel tailings reports — not evidence for hypotheses.
INSTRUCTION_FILE_MARKERS = (
    "как читать",
    "читать отчет",
    "читать отчёт",
)


def is_instruction_file(file_name: str) -> bool:
    lowered = (file_name or "").lower().replace("\\", "/")
    return any(marker in lowered for marker in INSTRUCTION_FILE_MARKERS)


def plant_name_for_case(case_id: str | None, subject: str) -> str:
    """Map case_id slugs to the same Plant label used in Excel triplets."""
    if case_id:
        for cid, display_name, _ in CASE_NAME_PATTERNS:
            if case_id == cid or subject == cid:
                return display_name
    return subject


def detect_case_from_path(path: Path) -> tuple[str, str] | None:
    name = path.name.lower()
    for case_id, display_name, pattern in CASE_NAME_PATTERNS:
        if pattern in name:
            return case_id, display_name

    parts = [part.lower().strip() for part in path.parts]
    for folder_key, case_info in sorted(
        CASE_FOLDER_MAP.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if any(part == folder_key for part in parts):
            return case_info
    return None


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def is_size_class_header(label: str) -> bool:
    normalized = normalize_label(label).lower()
    if "класс крупности" in normalized:
        return True
    if "мкм" in normalized and any(ch.isdigit() for ch in normalized):
        return True
    return False


def is_mineral_row(label: str) -> bool:
    normalized = normalize_label(label).lower()
    if normalized in MINERAL_NAMES:
        return True
    if "pnt/cp" in normalized:
        return True
    if "пирит/" in normalized:
        return True
    if "металл" in normalized and ("извлек" in normalized or "не извлек" in normalized):
        return True
    return False


def safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str) and not value.strip():
            return None
        result = float(value)
        if result != result:  # NaN
            return None
        return result
    except (TypeError, ValueError):
        return None
