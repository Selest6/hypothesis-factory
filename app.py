"""Фабрика гипотез — Streamlit UI (Part C)."""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import streamlit.components.v1 as components

from src.graph.scorer import ScoreWeights
from src.llm.pipeline import run_pipeline
from src.models.schemas import GeneratedHypothesis, PipelineResult
from src.rag.context import retrieve_context
from src.ui.export import result_to_json, result_to_markdown, save_feedback
from src.ui.kpi_diagnostics import diagnose_kpi
from src.ui.labels import format_context_label
from src.ui.mini_graph import build_mini_graph_html
from src.ui.presets import CASE_PRESETS
from src.ui.styles import CUSTOM_CSS

st.set_page_config(
    page_title="Фабрика гипотез",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def init_state() -> None:
    defaults = {
        "result": None,
        "context_summary": None,
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
            <p>KPI-first генерация проверяемых гипотез для обогатительных фабрик.
            Диагностика потерь из Excel → RAG + граф → Yandex GPT → ранжирование с объяснениями.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str, str, str, str, ScoreWeights]:
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
        format_func=lambda m: "Demo (кэш, для жюри)" if m == "demo" else "Live (Yandex GPT)",
        index=0,
        help="Demo не требует API-ключа. Live — реальная генерация через Yandex GPT.",
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Веса ранжирования")
    w_novelty = st.sidebar.slider("Новизна", 0.0, 1.0, 0.25, 0.05)
    w_grounded = st.sidebar.slider("Обоснованность", 0.0, 1.0, 0.30, 0.05)
    w_value = st.sidebar.slider("Ценность KPI", 0.0, 1.0, 0.25, 0.05)
    w_risk = st.sidebar.slider("Штраф за риск", 0.0, 1.0, 0.20, 0.05)
    weights = ScoreWeights(
        novelty=w_novelty,
        groundedness=w_grounded,
        value=w_value,
        risk=w_risk,
    )

    st.sidebar.markdown("---")
    kpi_goal = st.sidebar.text_area("KPI-цель", value=preset["kpi_goal"], height=72)
    constraints = st.sidebar.text_area(
        "Ограничения",
        value=preset.get("constraints", ""),
        height=88,
    )

    if mode == "live":
        from src.llm.yandex_client import YandexGPTClient

        client = YandexGPTClient()
        if client.configured:
            st.sidebar.success("Yandex GPT подключён")
        else:
            st.sidebar.error("Нет API-ключа в .env")

    return case_id, kpi_goal, constraints, mode, weights


def render_context_info(case_id: str, kpi_goal: str) -> None:
    try:
        ctx = retrieve_context(case_id, kpi_goal)
        st.session_state.context_summary = {
            "backend": ctx.retrieval_backend,
            "format_examples": bool(ctx.format_examples),
            "chunks": len(ctx.text_chunks),
            "triplets": len(ctx.graph_triplets),
            "case_name": ctx.case_name,
        }
        info = st.session_state.context_summary
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Retrieval", info["backend"])
        c2.metric("Примеры формата", "да" if info["format_examples"] else "нет")
        c3.metric("Текстовых фрагментов", info["chunks"])
        c4.metric("Triplets в контексте", info["triplets"])
    except Exception as exc:
        st.caption(f"Контекст: {exc}")


def render_diagnostics(case_id: str, kpi_goal: str) -> None:
    st.markdown(
        '<span class="step-badge">Шаг 1</span> **Диагностика KPI** — авто-анализ потерь из Excel',
        unsafe_allow_html=True,
    )
    st.caption("Топ-3 строки Excel с наибольшими потерями металла в тоннах — без нейросети.")

    hotspots = diagnose_kpi(case_id, kpi_goal, top_n=3)
    if not hotspots:
        st.warning("Не найдены triplets с потерями для этого KPI.")
        return

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
        ("Новизна", s.novelty, "#8b5cf6"),
        ("Обоснованность", s.groundedness, "#3b82f6"),
        ("Ценность KPI", s.value, "#10b981"),
        ("Риск (инверс.)", 1.0 - s.risk, "#f59e0b"),
    ]
    cols = st.columns(4)
    for col, (label, val, _color) in zip(cols, labels):
        with col:
            st.caption(label)
            st.progress(min(max(val, 0.0), 1.0))
            st.write(f"**{val:.2f}**")


def render_novelty_badge(h: GeneratedHypothesis) -> None:
    if not h.prior_art_snippet:
        st.caption("Нет фрагмента литературы для сравнения новизны.")
        return
    sim = (h.prior_art_similarity or 0) * 100
    snippet = h.prior_art_snippet[:90] + ("…" if len(h.prior_art_snippet) > 90 else "")
    if (h.prior_art_similarity or 0) < 0.5:
        st.markdown(
            f'<div class="novelty-new">🆕 Ближайший фрагмент литературы: «{snippet}» — '
            f"сходство <b>{sim:.0f}%</b>. <b>Новое направление.</b></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="novelty-known">📚 Ближайший фрагмент литературы: «{snippet}» — '
            f"сходство <b>{sim:.0f}%</b>.</div>",
            unsafe_allow_html=True,
        )


def _format_risks(h: GeneratedHypothesis) -> tuple[str, str]:
    risks = h.risks
    if isinstance(risks, dict):
        return str(risks.get("technical", "—")), str(risks.get("economic", "—"))
    if isinstance(risks, list):
        return (str(risks[0]) if risks else "—", str(risks[1]) if len(risks) > 1 else "—")
    return "—", "—"


def render_hypothesis_card(h: GeneratedHypothesis, idx: int, case_id: str) -> None:
    total = h.scores.total if h.scores else 0.0
    st.markdown(
        f"""
        <div class="hypothesis-card">
            <div class="hypothesis-rank">#{idx} · итого {total:.2f}</div>
            <div class="hypothesis-title">{h.title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="statement-box">{h.full_statement}</div>', unsafe_allow_html=True)
    render_score_bars(h)
    render_novelty_badge(h)

    c1, c2 = st.columns(2)
    with c1:
        if h.mechanism:
            st.markdown("**Механизм**")
            st.write(h.mechanism)
        if h.kpi_impact:
            st.markdown("**Влияние на KPI**")
            st.write(h.kpi_impact)
    with c2:
        if h.score_explanations:
            with st.expander("Почему такие оценки?", expanded=False):
                for text in h.score_explanations.values():
                    st.markdown(f"- {text}")

    if h.sources:
        st.markdown("**📎 Доказательная база (источники)**")
        for src in h.sources:
            if hasattr(src, "model_dump"):
                data = src.model_dump()
            elif isinstance(src, dict):
                data = src
            else:
                data = {"file": str(src)}
            parts = [f"**{data.get('file', '—')}**"]
            if data.get("sheet"):
                parts.append(f"лист `{data['sheet']}`")
            if data.get("row"):
                parts.append(f"строка **{data['row']}**")
            if data.get("page"):
                parts.append(f"стр. {data['page']}")
            line = " · ".join(parts)
            frag = data.get("fragment")
            st.markdown(
                f'<div class="source-chip">{line}'
                + (f"<br><span style='color:#64748b'>{frag[:280]}</span>" if frag else "")
                + "</div>",
                unsafe_allow_html=True,
            )

    if h.verification_steps:
        st.markdown("**🧪 Шаги верификации**")
        for step in h.verification_steps:
            st.markdown(f"- {step}")

    tech, econ = _format_risks(h)
    st.markdown(f"**Риски:** техн. — {tech} | экон. — {econ}")

    fb1, fb2, _ = st.columns([1, 1, 4])
    with fb1:
        if st.button("👍 Полезно", key=f"up_{case_id}_{idx}"):
            save_feedback(case_id, h.title, "up")
            st.toast("Спасибо за фидбэк!")
    with fb2:
        if st.button("👎 Не подходит", key=f"down_{case_id}_{idx}"):
            save_feedback(case_id, h.title, "down")
            st.toast("Записано.")

    st.divider()


def render_results(result: PipelineResult, constraints: str) -> None:
    mode_class = "mode-demo" if result.mode.startswith("demo") else "mode-live"
    st.markdown(
        f'<span class="step-badge">Шаг 3</span> **Top-{len(result.hypotheses)} гипотез** '
        f'· режим <span class="{mode_class}">{result.mode}</span>',
        unsafe_allow_html=True,
    )
    if result.error:
        st.warning(f"API: {result.error}")

    for i, h in enumerate(result.hypotheses, 1):
        render_hypothesis_card(h, i, result.case_id)

    st.markdown("---")
    st.subheader("📤 Экспорт")
    md = result_to_markdown(result, constraints)
    js = result_to_json(result, constraints)
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "Скачать Markdown",
            md,
            file_name=f"hypotheses_{result.case_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "Скачать JSON",
            js,
            file_name=f"hypotheses_{result.case_id}.json",
            mime="application/json",
            use_container_width=True,
        )


def main() -> None:
    init_state()
    case_id, kpi_goal, constraints, mode, weights = render_sidebar()

    render_hero()
    render_context_info(case_id, kpi_goal)
    render_diagnostics(case_id, kpi_goal)

    with st.expander(
        "🕸️ Граф связей вокруг KPI (ТЗ: визуализация связей)",
        expanded=False,
    ):
        st.caption(
            "Показывает, как материалы, классы крупности, минералы и потери связаны между собой "
            "вокруг выбранного KPI. Не весь граф (2000+ узлов), а фрагмент ~20 узлов для наглядности."
        )
        try:
            html = build_mini_graph_html(case_id, kpi_goal)
            components.html(html, height=460, scrolling=True)
        except Exception as exc:
            st.warning(f"Граф временно недоступен: {exc}")

    st.markdown(
        '<span class="step-badge">Шаг 2</span> **Генерация гипотез**',
        unsafe_allow_html=True,
    )

    g1, g2 = st.columns([1, 2])
    with g1:
        generate = st.button("⚡ Сгенерировать гипотезы", type="primary", use_container_width=True)
    with g2:
        mode_hint = "Demo — из кэша, без API" if mode == "demo" else "Live — Yandex GPT"
        st.caption(f"{mode_hint} · **{CASE_PRESETS[case_id]['case_name']}**")

    if generate:
        with st.spinner("Генерация гипотез… (до 2–3 мин в Live-режиме)"):
            try:
                result = run_pipeline(
                    case_id,
                    kpi_goal=kpi_goal,
                    constraints=constraints,
                    mode=mode,  # type: ignore[arg-type]
                    weights=weights,
                    save_demo_cache=True,
                )
                st.session_state.result = result
                st.session_state.last_case = case_id
                if result.mode == "demo":
                    st.success("Загружено из Demo-кэша")
                elif result.mode == "demo_fallback":
                    st.warning("API недоступен — показан Demo-кэш")
                else:
                    st.success(f"Сгенерировано {len(result.hypotheses)} гипотез")
            except Exception as exc:
                st.error(
                    f"Ошибка: {exc}\n\n"
                    "Для Demo: `python scripts/build_demo_cache.py --offline`"
                )

    result: PipelineResult | None = st.session_state.result
    if result and result.case_id == case_id and result.hypotheses:
        st.markdown("---")
        render_results(result, constraints)
    elif result and result.case_id != case_id:
        st.info("Нажмите «Сгенерировать» для выбранного кейса.")


if __name__ == "__main__":
    main()
