from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.graph.builder import GraphBuilder, normalize_element
from src.models.schemas import GeneratedHypothesis, SourceRef

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"

GENERIC_SUBJECTS = frozenset(
    {
        "отвальные хвосты",
        "шихта руд",
        "материал пруда - накопителя",
        "итого извлекаемый металл",
        "извлекаемый металл",
        "потери (расписать)",
        "свободный слот",
    }
)

# Шаблоны вмешательств по типу минерала / проблемы (не из docx-гипотез).
INTERVENTION_RULES: list[dict[str, Any]] = [
    {
        "match": ("закрыт",),
        "actions": [
            "доизмельчение класса {size} для раскрытия {mineral} перед контрольной флотацией",
            "дополнительная стадия измельчения питания класса {size} с целью раскрытия {mineral}",
        ],
        "mechanism": (
            "Недораскрытый {mineral} в классе {size} уходит в хвосты; "
            "дополнительное измельчение повышает степень раскрытия и доступность для флотации."
        ),
        "lit_keywords": ("измельч", "раскрыт", "крупн"),
    },
    {
        "match": ("раскрыт", "pnt"),
        "actions": [
            "увеличение времени контакта реагентов для класса {size} с {mineral}",
            "коррекция режима флотации для удержания {mineral} из класса {size}",
        ],
        "mechanism": (
            "Раскрытый {mineral} в классе {size} уже доступен, но теряется из-за режима флотации; "
            "коррекция контактного времени и плотности пульпы снизит унос в хвосты."
        ),
        "lit_keywords": ("флотац", "реагент", "пульп"),
    },
    {
        "match": ("миллерит",),
        "actions": [
            "магнитная сепарация над классом {size} для извлечения {mineral}",
            "добавление магнитной сепарации в схему перед хвостами для класса {size}",
        ],
        "mechanism": (
            "{mineral} в классе {size} обладает магнитными свойствами; "
            "магнитная сепарация позволит извлечь часть потерь до отвала."
        ),
        "lit_keywords": ("магнит", "сепарац"),
    },
    {
        "match": ("силикат", "валлериит"),
        "actions": [
            "усиленная депрессия силикатов в классе {size} при флотации {element}",
            "коррекция дозировки депрессора для снижения уноса {mineral} из класса {size}",
        ],
        "mechanism": (
            "Силикатная форма {mineral} в классе {size} конкурирует за поверхность пузырьков; "
            "депрессия силикатов улучшит избирательность флотации {element}."
        ),
        "lit_keywords": ("депресс", "силикат", "избирательн"),
    },
]

DEFAULT_ACTIONS = [
    "дополнительная классификация класса {size} с возвратом песков на доизмельчение",
    "оптимизация схемы классификации для класса {size} с фокусом на {mineral}",
]

LITERATURE_TECHNIQUES = [
    ("гидроциклон", "замена или донастройка гидроциклонов для класса {size}"),
    ("классификац", "усиленная классификация класса {size} перед флотацией"),
    ("измельч", "изменение режима измельчения для снижения крупности класса {size}"),
    ("флотац", "коррекция флотационного режима для минерала {mineral} в классе {size}"),
    ("реагент", "подбор реагентовой схемы для {mineral} в классе {size}"),
]


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _is_reference_source(file_name: str) -> bool:
    lowered = file_name.lower()
    return "гипотез" in lowered or "hypothesis" in lowered


def _pick_rule(mineral: str) -> dict[str, Any]:
    lowered = mineral.lower()
    for rule in INTERVENTION_RULES:
        if any(token in lowered for token in rule["match"]):
            return rule
    return {}


def _pick_literature_snippet(
    processed_dir: Path,
    keywords: tuple[str, ...],
    *,
    max_len: int = 200,
) -> tuple[str, SourceRef] | None:
    for rel in ("literature/chunks.json", "instructions/chunks.json"):
        for chunk in _load_json(processed_dir / rel):
            text = (chunk.get("text") or "").lower()
            if not any(kw in text for kw in keywords):
                continue
            src = chunk.get("source") or {}
            file_name = str(src.get("file") or "")
            if _is_reference_source(file_name):
                continue
            return (chunk.get("text") or "")[:max_len], SourceRef(
                file=file_name or "требует верификации",
                sheet=src.get("sheet"),
                row=src.get("row"),
                page=src.get("page"),
                fragment=(chunk.get("text") or "")[:120],
            )
    return None


def _literature_action(processed_dir: Path, mineral: str, size: str) -> tuple[str, SourceRef | None]:
    mineral_l = mineral.lower()
    for kw, template in LITERATURE_TECHNIQUES:
        if kw in mineral_l or kw in size.lower():
            snippet = _pick_literature_snippet(processed_dir, (kw,))
            if snippet:
                text, src = snippet
                return template.format(mineral=mineral, size=size), src
    snippet = _pick_literature_snippet(processed_dir, ("флотац", "классификац", "измельч"))
    if snippet:
        _, src = snippet
        return DEFAULT_ACTIONS[0].format(mineral=mineral, size=size), src
    return DEFAULT_ACTIONS[1].format(mineral=mineral, size=size), None


def _group_mineral_losses(
    case_id: str,
    processed_dir: Path,
    element: str,
) -> list[dict[str, Any]]:
    triplets = _load_json(processed_dir / "cases" / case_id / "triplets.json")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for trip in triplets:
        if trip.get("case_id") != case_id:
            continue
        src = trip.get("source") or {}
        row = src.get("row")
        if row is None:
            continue
        key = (row, trip.get("subject", ""))
        bucket = by_key.setdefault(
            key,
            {
                "mineral": trip["subject"],
                "size_class": None,
                "element": element,
                "loss_tons": None,
                "loss_percent": None,
                "extractable_tons": None,
                "source": src,
            },
        )
        pred = trip.get("predicate")
        meta = trip.get("metadata") or {}
        if pred == "found_in":
            bucket["size_class"] = trip.get("object")
        elif pred == "loses_to" and meta.get("element") == element:
            if meta.get("metric_kind") == "loss_tons":
                bucket["loss_tons"] = meta.get("value")
            elif meta.get("metric_kind") == "loss_percent":
                bucket["loss_percent"] = meta.get("value")
                if not bucket["size_class"]:
                    bucket["size_class"] = meta.get("context")
        elif pred == "potentially_extractable" and meta.get("tons") is not None:
            bucket["extractable_tons"] = meta.get("tons")

    rows = [r for r in by_key.values() if r.get("loss_tons") and float(r["loss_tons"]) > 0]
    # Сначала минералы с потенциалом извлечения, не агрегаты вроде «Отвальные хвосты».
    mineral_rows = [
        r
        for r in rows
        if r.get("extractable_tons")
        and r["mineral"].lower().strip() not in GENERIC_SUBJECTS
    ]
    mineral_rows.sort(key=lambda r: float(r["loss_tons"]), reverse=True)
    if mineral_rows:
        return mineral_rows
    rows = [r for r in rows if r["mineral"].lower().strip() not in GENERIC_SUBJECTS]
    rows.sort(key=lambda r: float(r["loss_tons"]), reverse=True)
    return rows


def build_synthesis_candidates(
    case_id: str,
    kpi_goal: str = "",
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    n_candidates: int = 10,
) -> list[GeneratedHypothesis]:
    """Синтез новых гипотез из Excel + графа + литературы (без docx-эталонов)."""
    processed_dir = Path(processed_dir)
    element = normalize_element(kpi_goal) or "Элемент 28"
    kpi = kpi_goal or f"снизить потери {element} в хвостах"

    mineral_rows = _group_mineral_losses(case_id, processed_dir, element)
    candidates: list[GeneratedHypothesis] = []
    seen_titles: set[str] = set()

    for row in mineral_rows:
        mineral = row["mineral"]
        size = row.get("size_class") or "целевого класса"
        tons = float(row["loss_tons"])
        percent = row.get("loss_percent")
        src = row.get("source") or {}

        rule = _pick_rule(mineral)
        actions = rule.get("actions") or DEFAULT_ACTIONS
        action_idx = len(candidates) % len(actions)
        action = actions[action_idx].format(mineral=mineral, size=size, element=element)

        lit_action, lit_src = _literature_action(processed_dir, mineral, size)
        if len(candidates) % 2 == 1:
            action = lit_action

        percent_part = f" ({percent:.1f}% в классе)" if percent else ""
        title = f"{action[:1].upper()}{action[1:72].rstrip()} — {mineral}, класс {size}"
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        mechanism = rule.get("mechanism") or (
            f"В классе {size} теряется {tons:.0f} т {element} в связи с {mineral}; "
            f"целенаправленное вмешательство в этот узел снизит унос в хвосты."
        )
        mechanism = mechanism.format(mineral=mineral, size=size, element=element)

        sources = [
            SourceRef(
                file=str(src.get("file") or "требует верификации"),
                sheet=src.get("sheet"),
                row=src.get("row"),
                page=src.get("page"),
                fragment=f"{mineral}, класс {size}",
            )
        ]
        if lit_src:
            sources.append(lit_src)

        candidates.append(
            GeneratedHypothesis(
                title=title,
                full_statement=(
                    f"Если {action}, то потери {element} в хвостах снизятся, "
                    f"потому что {mineral} в классе {size} даёт {tons:.0f} т потерь{percent_part} "
                    f"по данным Excel (строка {src.get('row', '?')})."
                ),
                mechanism=mechanism,
                kpi_impact=f"Потенциальное снижение потерь {element} на участке с {tons:.0f} т в классе {size}.",
                verification_steps=[
                    f"Замерить содержание {element} в хвостах класса {size} до/после вмешательства.",
                    f"Провести минералогический анализ {mineral} в пробах класса {size}.",
                ],
                sources=sources,
                risks=[
                    "Изменение режима может повлиять на соседние классы крупности.",
                    "Требуется пилот для оценки CAPEX/OPEX и простоев.",
                ],
            )
        )
        if len(candidates) >= n_candidates:
            break

    if len(candidates) < n_candidates:
        graph = GraphBuilder.from_processed_dir(processed_dir, case_id=case_id)
        for loss in graph.loss_metrics(case_id=case_id, element=element)[:5]:
            subject = loss.get("subject", "узел")
            value = float(loss.get("value") or 0)
            context = loss.get("context") or "хвосты"
            src = loss.get("source") or {}
            title = f"Перераспределение нагрузки на участке «{subject[:40]}»"
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            candidates.append(
                GeneratedHypothesis(
                    title=title,
                    full_statement=(
                        f"Если перераспределить нагрузку на участке «{subject}» ({context}), "
                        f"то потери {element} ({value:.0f} т) в хвостах снизятся, "
                        f"потому что этот узел — один из лидеров по потерям в отчёте Excel."
                    ),
                    mechanism=(
                        f"Узел «{subject}» концентрирует {value:.0f} т потерь {element}; "
                        f"балансировка нагрузки и режима на этом участке снизит некондицию."
                    ),
                    kpi_impact=f"Снижение потерь {element} с участка «{subject}» (пилотный замер).",
                    verification_steps=[
                        f"A/B-тест режима на участке «{subject}».",
                        f"Контроль содержания {element} в хвостах 3–5 смен.",
                    ],
                    sources=[
                        SourceRef(
                            file=str(src.get("file") or "требует верификации"),
                            sheet=src.get("sheet"),
                            row=src.get("row"),
                            fragment=subject,
                        )
                    ],
                    risks=[
                        "Риск ухудшения показателей на соседних операциях.",
                        "Нужна согласованность с текущей схемой флотации.",
                    ],
                )
            )
            if len(candidates) >= n_candidates:
                break

    return candidates[:n_candidates]


def format_synthesis_hints(candidates: list[GeneratedHypothesis], *, max_items: int = 5) -> str:
    if not candidates:
        return "Нет автоматически собранных направлений."
    lines = []
    for i, item in enumerate(candidates[:max_items], 1):
        src = item.sources[0] if item.sources else None
        loc = ""
        if src:
            loc = f" [{src.file}, строка {src.row}]" if src.row else f" [{src.file}]"
        lines.append(f"{i}. {item.title}{loc}")
        lines.append(f"   Набросок: {item.full_statement[:220]}...")
    return "\n".join(lines)
