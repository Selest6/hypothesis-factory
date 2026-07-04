from __future__ import annotations

ALL_CASES_ID = "all"

CASE_IDS: tuple[str, ...] = ("kgmk", "nof_med", "nof_vkr", "tof")

CASE_NAMES: dict[str, str] = {
    "kgmk": "КГМК",
    "nof_med": "НОФ мед",
    "nof_vkr": "НОФ вкр",
    "tof": "ТОФ",
}


def is_all_cases(case_id: str) -> bool:
    return case_id == ALL_CASES_ID


def resolve_graph_case_id(case_id: str) -> str:
    """Cache/load key for GraphBuilder: empty string = all triplets."""
    return "" if is_all_cases(case_id) else case_id


def iter_case_ids(case_id: str) -> tuple[str, ...]:
    if is_all_cases(case_id):
        return CASE_IDS
    return (case_id,)


def matches_case(data_case_id: str | None, query_case_id: str) -> bool:
    if is_all_cases(query_case_id):
        return True
    return data_case_id in (query_case_id, None)


def case_display_name(case_id: str) -> str:
    if is_all_cases(case_id):
        return "Все кейсы"
    return CASE_NAMES.get(case_id, case_id)
