"""Фабрика гипотез — Streamlit UI (Part C)."""
from __future__ import annotations

from dataclasses import asdict

from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import streamlit.components.v1 as components

from src.graph.scorer import ScoreWeights
from src.llm.pipeline import refine_hypothesis_in_result, run_pipeline
from src.llm.web_sources import enrich_result_web
from src.models.schemas import GeneratedHypothesis, PipelineResult
from src.ui.display import escape_html_text, format_novelty_badge_html
from src.ui.export import (
    result_to_csv,
    result_to_docx_bytes,
    result_to_json,
    result_to_markdown,
    result_to_pdf_bytes,
    save_feedback,
)
from src.ui.kpi_diagnostics import KpiHotspot, diagnose_kpi
from src.ui.labels import format_context_label
from src.ui.mini_graph import build_mini_graph_html
from src.ui.presets import CASE_PRESETS
from src.ui.ensure_sources import download_sources_if_missing, sources_ready
from src.ui.source_downloads import normalize_source_filename, prepare_source_download, split_source_location
from src.ui.styles import CUSTOM_CSS

st.set_page_config(
    page_title="Фабрика гипотез",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_diagnose(case_id: str, kpi_goal: str, top_n: int = 3) -> list[dict]:
    return [asdict(spot) for spot in diagnose_kpi(case_id, kpi_goal, top_n=top_n)]


@st.cache_data(show_spinner=False, ttl=3600)
def cached_mini_graph_html(case_id: str, kpi_goal: str) -> str:
    return build_mini_graph_html(case_id, kpi_goal)


def init_state() -> None:
    defaults = {
        "result": None,
        "last_case": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>🏭 Фабрика гипотез</h1>
            <p>Системная генерация и приоритизация проверяемых гипотез для НИИ и промышленных лабораторий.
            Анализ потерь из отчётов Excel → база знаний (PDF, docx) → ранжирование с обоснованием и источниками.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_howto(mode: str) -> None:
    mode_line = (
        "Demo — готовые результаты без API-ключа."
        if mode == "demo"
        else "Live — генерация через Yandex GPT (нужен API-ключ в Secrets)."
    )
    st.markdown(
        f"""
        <div class="howto">
        <b>Как пользоваться:</b> выберите кейс и KPI → нажмите «Сгенерировать гипотезы» →
        изучите карточки, граф и экспорт отчёта. {mode_line}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str, str, str, str, ScoreWeights, bool, bool]:
    st.sidebar.title("⚙️ Настройки")

    case_id = st.sidebar.selectbox(
        "Кейс",
        options=list(CASE_PRESETS.keys()),
        format_func=lambda cid: CASE_PRESETS[cid]["case_name"],
    )
    preset = CASE_PRESETS[case_id]

    mode = st.sidebar.radio(
        "Режим",
        options=["demo", "live"],
        format_func=lambda m: "Demo (без API)" if m == "demo" else "Live (Yandex GPT)",
        index=0,
        help="Demo — для жюри, без ключа. Live — реальная генерация через Yandex GPT.",
    )

    st.sidebar.markdown("---")
    use_web = st.sidebar.checkbox(
        "🌐 Дополнить контекст из интернета",
        value=False,
        help="Бесплатный поиск DuckDuckGo. Ссылки появятся в блоке «Источники из интернета» и в каждой гипотезе.",
    )

    kpi_goal = st.sidebar.text_area("KPI-цель", value=preset["kpi_goal"], height=72)
    constraints = st.sidebar.text_area(
        "Ограничения",
        value=preset.get("constraints", ""),
        height=88,
    )

    with st.sidebar.expander("⚙️ Экспертная настройка — веса ранжирования", expanded=False):
        w_novelty = st.slider("Новизна", 0.0, 1.0, 0.25, 0.05)
        w_grounded = st.slider("Обоснованность", 0.0, 1.0, 0.30, 0.05)
        w_value = st.slider("Ценность KPI", 0.0, 1.0, 0.25, 0.05)
        w_risk = st.slider("Штраф за риск", 0.0, 1.0, 0.20, 0.05)

    weights = ScoreWeights(
        novelty=w_novelty,
        groundedness=w_grounded,
        value=w_value,
        risk=w_risk,
    )

    if mode == "live":
        import os

        if os.getenv("YANDEX_API_KEY") or os.getenv("YANDEX_FOLDER_ID"):
            st.sidebar.success("Yandex GPT: ключ найден")
        else:
            st.sidebar.warning("Live недоступен без API-ключа (Streamlit Secrets или .env)")

    return case_id, kpi_goal, constraints, mode, weights, use_web


def render_generate_button(
    case_id: str,
    kpi_goal: str,
    constraints: str,
    mode: str,
    weights: ScoreWeights,
    use_web: bool = False,
) -> None:
    st.markdown(
        '<span class="step-badge">Шаг 1</span> **Сгенерировать гипотезы**',
        unsafe_allow_html=True,
    )
    g1, g2 = st.columns([1, 2])
    with g1:
        clicked = st.button(
            "⚡ Сгенерировать гипотезы",
            type="primary",
            use_container_width=True,
            key="generate_hypotheses",
        )
    with g2:
        mode_hint = "Demo — без API, ~1 сек" if mode == "demo" else "Live — Yandex GPT, до 2–3 мин"
        st.caption(f"{mode_hint} · **{CASE_PRESETS[case_id]['case_name']}**")

    if clicked:
        spinner_text = (
            "Загружаем готовые гипотезы…"
            if mode == "demo"
            else "Формируем гипотезы через Yandex GPT… (до 2–3 мин)"
        )
        with st.spinner(spinner_text):
            try:
                result = run_pipeline(
                    case_id,
                    kpi_goal=kpi_goal,
                    constraints=constraints,
                    mode=mode,  # type: ignore[arg-type]
                    weights=weights,
                    save_demo_cache=False,
                    use_web=use_web,
                )
                st.session_state.result = result
                st.session_state.last_case = case_id
                if result.mode == "demo":
                    st.success(f"Готово: {len(result.hypotheses)} гипотез (Demo)")
                elif result.mode == "demo_fallback":
                    st.warning("API недоступен — показан Demo-кэш")
                else:
                    st.success(f"Сгенерировано {len(result.hypotheses)} гипотез")
            except Exception as exc:
                st.error(f"Ошибка: {exc}")


def render_diagnostics(case_id: str, kpi_goal: str) -> None:
    st.markdown(
        '<span class="step-badge">Шаг 3</span> **Диагностика KPI** — где теряется металл',
        unsafe_allow_html=True,
    )
    st.caption("Топ-3 строки Excel с наибольшими потерями — автоматически, без нейросети.")

    raw = cached_diagnose(case_id, kpi_goal, top_n=3)
    if not raw:
        st.warning("Не найдены triplets с потерями для этого KPI.")
        return

    hotspots = [KpiHotspot(**row) for row in raw]
    cols = st.columns(len(hotspots))
    for col, spot in zip(cols, hotspots):
        with col:
            loc = spot.source_file
            if spot.source_sheet:
                loc += f", лист «{spot.source_sheet}»"
            if spot.source_row:
                loc += f", строка {spot.source_row}"

            context_label = format_context_label(spot.context)

            st.markdown(
                f"""
                <div class="hotspot-card">
                    <div class="hotspot-value">{spot.value:,.0f} {spot.unit}</div>
                    <div class="hotspot-label">{spot.element} · {context_label}<br>{spot.subject[:55]}</div>
                    <div class="hotspot-source">📄 {loc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_score_bars(h: GeneratedHypothesis) -> None:
    if not h.scores:
        return
    s = h.scores
    labels = [
        ("Новизна", s.novelty),
        ("Обоснованность", s.groundedness),
        ("Ценность KPI", s.value),
        ("Риск (инверс.)", 1.0 - s.risk),
    ]
    cols = st.columns(4)
    for col, (label, val) in zip(cols, labels):
        with col:
            st.caption(label)
            st.progress(min(max(val, 0.0), 1.0))
            st.write(f"**{val:.2f}**")


def render_novelty_badge(h: GeneratedHypothesis) -> None:
    if not h.prior_art_snippet:
        return
    st.markdown(
        format_novelty_badge_html(
            similarity=h.prior_art_similarity or 0,
            snippet=h.prior_art_snippet,
        ),
        unsafe_allow_html=True,
    )


def _format_risks(h: GeneratedHypothesis) -> tuple[str, str]:
    risks = h.risks
    if isinstance(risks, dict):
        return str(risks.get("technical", "—")), str(risks.get("economic", "—"))
    if isinstance(risks, list):
        return (str(risks[0]) if risks else "—", str(risks[1]) if len(risks) > 1 else "—")
    return "—", "—"


def render_hypothesis_card(
    h: GeneratedHypothesis,
    idx: int,
    case_id: str,
    *,
    result: PipelineResult,
    constraints: str,
    weights: ScoreWeights,
    mode: str,
    use_web: bool,
) -> None:
    total = h.scores.total if h.scores else 0.0
    title = escape_html_text(h.title)
    statement = escape_html_text(h.full_statement)
    st.markdown(
        f"""
        <div class="hypothesis-card">
            <div class="hypothesis-rank">#{idx} · итого {total:.2f}</div>
            <div class="hypothesis-title">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="statement-box">{statement}</div>', unsafe_allow_html=True)
    render_score_bars(h)
    render_novelty_badge(h)

    if h.mechanism:
        st.markdown("**Механизм**")
        st.markdown(f'<div class="hypothesis-body">{escape_html_text(h.mechanism)}</div>', unsafe_allow_html=True)
    if h.kpi_impact:
        st.markdown("**Влияние на KPI**")
        st.markdown(f'<div class="hypothesis-body">{escape_html_text(h.kpi_impact)}</div>', unsafe_allow_html=True)
    if h.score_explanations:
        with st.expander("Почему такие оценки?", expanded=False):
            for text in h.score_explanations.values():
                st.markdown(f"- {text}")

    if h.sources:
        st.markdown("**📎 Источники**")
        for src_idx, src in enumerate(h.sources):
            data = split_source_location(src, case_id=case_id)
            file_label = str(data.get("file") or "—")
            if file_label.startswith("http"):
                safe_url = escape_html_text(file_label)
                parts = [
                    f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'
                ]
            else:
                parts = [f"**{file_label}**"]
            if data.get("sheet"):
                parts.append(f"лист `{data['sheet']}`")
            if data.get("row"):
                parts.append(f"строка **{data['row']}**")
            if data.get("page"):
                parts.append(f"стр. {data['page']}")
            line = " · ".join(parts)
            frag = data.get("fragment")
            frag_html = (
                f"<br><span style='color:#64748b'>{escape_html_text(str(frag))}</span>"
                if frag
                else ""
            )

            src_col, btn_col = st.columns([5, 1])
            with src_col:
                st.markdown(
                    f'<div class="source-chip">{line}{frag_html}</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                file_name = normalize_source_filename(data, case_id=case_id)
                cached = cached_source_download(file_name) if file_name else None
                if cached:
                    data_bytes, dl_name, mime = cached
                    st.download_button(
                        "⬇",
                        data_bytes,
                        file_name=dl_name,
                        mime=mime,
                        key=f"src_dl_{case_id}_{idx}_{src_idx}",
                        help=f"Скачать полный файл {dl_name}",
                    )
                elif file_name.startswith("http"):
                    st.link_button(
                        "🔗",
                        file_name,
                        help="Открыть ссылку",
                        key=f"src_link_{case_id}_{idx}_{src_idx}",
                    )
                elif file_name and file_name not in {"—", "требует верификации"}:
                    st.caption("нет файла")

    if h.verification_steps:
        st.markdown("**🧪 Шаги верификации**")
        for step in h.verification_steps:
            st.markdown(f"- {step}")

    tech, econ = _format_risks(h)
    st.markdown(f"**Риски:** техн. — {tech} | экон. — {econ}")

    st.markdown("**✏️ Доработка гипотезы**")
    comment = st.text_area(
        "Что не так / что улучшить?",
        key=f"fb_comment_{case_id}_{idx}",
        height=68,
        placeholder="Например: слишком общая формулировка, нет связи с конкретной строкой Excel…",
    )

    refine_clicked = st.button(
        "🔄 Переделать с учётом замечания",
        key=f"refine_{case_id}_{idx}",
        type="secondary",
    )

    if refine_clicked:
        if mode == "demo":
            st.warning("Переделка по фидбеку доступна только в режиме **Live** (Yandex GPT).")
        elif not comment.strip():
            st.warning("Напишите, что не так — без замечания модель не поймёт, что улучшать.")
        else:
            with st.spinner("Улучшаем гипотезу с учётом замечания и прошлых отзывов…"):
                try:
                    updated = refine_hypothesis_in_result(
                        result,
                        idx - 1,
                        comment.strip(),
                        constraints=constraints,
                        weights=weights,
                        use_web=use_web,
                    )
                    save_feedback(
                        case_id,
                        h.title,
                        "down",
                        comment.strip(),
                        extra={
                            "action": "refine",
                            "refined_title": updated.hypotheses[idx - 1].title,
                        },
                    )
                    st.session_state.result = updated
                    st.success("Гипотеза обновлена и пересчитана.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Не удалось переделать: {exc}")

    st.divider()


def render_web_sources(result: PipelineResult) -> None:
    snippets = (result.context_summary or {}).get("web_snippets") or []
    if not snippets:
        return

    st.markdown("**🌐 Источники из интернета**")
    if (result.context_summary or {}).get("web_fallback"):
        st.caption("DuckDuckGo с сервера недоступен — показаны проверенные открытые ссылки на литературу.")
    else:
        st.caption("DuckDuckGo · бесплатно · требует верификации")
    for item in snippets:
        title = escape_html_text(str(item.get("title") or "Источник"))
        url = str(item.get("url") or "").strip()
        snippet = escape_html_text(str(item.get("snippet") or "")[:240])
        if not url:
            continue
        safe_url = escape_html_text(url)
        st.markdown(
            f'<div class="web-link-item">'
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            f'<div class="web-link-snippet">{snippet}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render_results(
    result: PipelineResult,
    constraints: str,
    *,
    weights: ScoreWeights,
    mode: str,
    use_web: bool,
) -> None:
    mode_class = "mode-demo" if result.mode.startswith("demo") else "mode-live"
    st.markdown(
        f'<span class="step-badge">Шаг 2</span> **Top-{len(result.hypotheses)} гипотез** '
        f'· <span class="{mode_class}">{result.mode}</span>',
        unsafe_allow_html=True,
    )
    if result.error:
        st.warning(f"API: {result.error}")

    if use_web and not (result.context_summary or {}).get("web_enriched"):
        result = enrich_result_web(result)
        st.session_state.result = result

    render_web_sources(result)

    for i, h in enumerate(result.hypotheses, 1):
        render_hypothesis_card(
            h,
            i,
            result.case_id,
            result=result,
            constraints=constraints,
            weights=weights,
            mode=mode,
            use_web=use_web,
        )

    st.markdown("---")
    st.subheader("📤 Экспорт отчёта")
    st.caption("Бизнес-отчёт с ранжированием гипотез и KPI (ТЗ: PDF/DOCX/CSV/JSON).")

    md = result_to_markdown(result, constraints)
    js = result_to_json(result, constraints)
    csv_data = result_to_csv(result, constraints)

    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "CSV",
            csv_data,
            file_name=f"hypotheses_{result.case_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "JSON",
            js,
            file_name=f"hypotheses_{result.case_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "Markdown",
            md,
            file_name=f"hypotheses_{result.case_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    if st.checkbox("Подготовить PDF и DOCX", value=False, key=f"heavy_export_{result.case_id}"):
        with st.spinner("Формируем PDF и DOCX…"):
            docx_bytes = result_to_docx_bytes(result, constraints)
            pdf_bytes = result_to_pdf_bytes(result, constraints)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "PDF",
                pdf_bytes,
                file_name=f"hypotheses_{result.case_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "DOCX",
                docx_bytes,
                file_name=f"hypotheses_{result.case_id}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )


@st.cache_data(show_spinner=False, ttl=86400)
def cached_source_download(file_name: str) -> tuple[bytes, str, str] | None:
    payload = prepare_source_download({"file": file_name}, fetch_remote=True)
    if not payload:
        return None
    return payload.data, payload.filename, payload.mime


@st.cache_resource
def _ensure_source_files() -> bool:
    return download_sources_if_missing()


def main() -> None:
    init_state()
    if not sources_ready():
        with st.spinner("Загружаем исходные документы с Яндекс.Диска…"):
            ready = _ensure_source_files()
        if not ready:
            st.warning(
                "Не удалось загрузить исходные файлы. "
                "Запустите: `python scripts/download_yandex_disk_sources.py`"
            )

    case_id, kpi_goal, constraints, mode, weights, use_web = render_sidebar()

    render_hero()
    render_howto(mode)
    render_generate_button(case_id, kpi_goal, constraints, mode, weights, use_web)

    result: PipelineResult | None = st.session_state.result
    if result and result.case_id == case_id and result.hypotheses:
        st.markdown("---")
        render_results(result, constraints, weights=weights, mode=mode, use_web=use_web)
    elif result and result.case_id != case_id:
        st.info("Нажмите «Сгенерировать гипотезы» для выбранного кейса.")

    st.markdown("---")
    render_diagnostics(case_id, kpi_goal)

    if st.checkbox("🕸️ Показать граф связей вокруг KPI", value=False, key="show_graph"):
        st.caption(
            "Фрагмент графа знаний (~20 узлов): материалы, классы крупности, минералы и потери "
            "вокруг выбранного KPI."
        )
        try:
            html = cached_mini_graph_html(case_id, kpi_goal)
            components.html(html, height=460, scrolling=True)
        except Exception as exc:
            st.warning(f"Граф временно недоступен: {exc}")


if __name__ == "__main__":
    main()
