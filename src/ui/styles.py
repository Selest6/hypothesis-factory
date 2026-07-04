CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Компактнее контент, но toolbar (Deploy ⋮) оставляем */
header[data-testid="stHeader"] {
    background: transparent;
}

section.main > div.block-container,
div[data-testid="stMainBlockContainer"] > div.block-container,
.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 1rem;
    max-width: 100%;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1rem;
}
[data-testid="stMetric"] {
    background: transparent;
}
hr {
    margin: 0.75rem 0;
}

.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
}

.hero-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.hero h1 { margin: 0; font-size: 1.5rem; color: #f8fafc; line-height: 1.2; }

.hero-lead {
    margin: 0.65rem 0 0;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.45;
}

.hero-lead b { color: #e2e8f0; font-weight: 600; }

.hero-case {
    margin-top: 0.75rem;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid #334155;
    border-radius: 999px;
    padding: 0.35rem 0.85rem;
}

.hero-case-label {
    color: #64748b;
    font-size: 0.78rem;
}

.hero-case-name {
    color: #93c5fd;
    font-size: 0.85rem;
    font-weight: 600;
}

.mode-pill {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    white-space: nowrap;
}

.mode-pill-demo {
    background: #064e3b;
    color: #6ee7b7;
    border: 1px solid #059669;
}

.mode-pill-live {
    background: #1e3a5f;
    color: #93c5fd;
    border: 1px solid #3b82f6;
}

.howto-flow {
    display: flex;
    align-items: stretch;
    gap: 0.5rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
}

.howto-step {
    flex: 1 1 160px;
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 0.75rem 0.85rem;
}

.howto-num {
    flex-shrink: 0;
    width: 1.6rem;
    height: 1.6rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #2563eb;
    color: white;
    font-size: 0.8rem;
    font-weight: 700;
    border-radius: 999px;
}

.howto-title {
    color: #f1f5f9;
    font-size: 0.88rem;
    font-weight: 600;
    line-height: 1.3;
}

.howto-desc {
    color: #94a3b8;
    font-size: 0.78rem;
    margin-top: 0.15rem;
    line-height: 1.35;
}

.howto-arrow {
    display: flex;
    align-items: center;
    color: #475569;
    font-size: 1.1rem;
    padding: 0 0.15rem;
}

.step-panel {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem 1.15rem 0.85rem;
    margin-bottom: 0.85rem;
}

.step-panel-muted {
    background: #172033;
    border-style: dashed;
}

.step-title {
    color: #f1f5f9;
    font-size: 1.05rem;
    font-weight: 600;
    vertical-align: middle;
}

.step-subtitle {
    color: #94a3b8;
    font-size: 0.88rem;
    margin: 0.35rem 0 0.85rem;
    line-height: 1.4;
}

.step-hint {
    color: #64748b;
    font-size: 0.82rem;
    margin: 0.65rem 0 0;
    line-height: 1.4;
}

.step-badge-muted {
    background: #475569;
}

.step-badge {
    display: inline-block;
    background: #2563eb;
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    margin-right: 0.5rem;
    vertical-align: middle;
}

.hotspot-card {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 1rem;
    height: 100%;
}

.hotspot-value {
    font-size: 1.6rem;
    font-weight: 600;
    color: #fbbf24;
    line-height: 1.2;
}

.hotspot-label {
    color: #cbd5e1;
    font-size: 0.85rem;
    margin-top: 0.35rem;
}

.hotspot-source {
    color: #64748b;
    font-size: 0.78rem;
    margin-top: 0.5rem;
}

.hotspot-hint {
    color: #94a3b8;
    font-size: 0.78rem;
    margin-top: 0.45rem;
    line-height: 1.35;
    font-style: italic;
}

.hotspot-section {
    color: #cbd5e1;
    font-size: 0.82rem;
    margin-top: 0.25rem;
}

.hypothesis-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}

.hypothesis-rank {
    color: #60a5fa;
    font-weight: 600;
    font-size: 0.85rem;
}

.hypothesis-title {
    color: #f1f5f9;
    font-size: 1.15rem;
    font-weight: 600;
    margin: 0.25rem 0 0.75rem;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    line-height: 1.45;
}

.statement-box {
    background: #0f172a;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    color: #e2e8f0;
    font-style: italic;
    border-left: 3px solid #6366f1;
    margin-bottom: 1rem;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    line-height: 1.55;
}

.hypothesis-body {
    color: #e2e8f0;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    line-height: 1.5;
}

.novelty-new {
    background: #064e3b;
    border: 1px solid #059669;
    border-radius: 8px;
    padding: 0.75rem 0.9rem;
    color: #d1fae5;
    font-size: 0.92rem;
    line-height: 1.45;
}

.novelty-known {
    background: #451a03;
    border: 1px solid #d97706;
    border-radius: 8px;
    padding: 0.75rem 0.9rem;
    color: #fde68a;
    font-size: 0.92rem;
    line-height: 1.45;
}

.source-chip {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.4rem;
    font-size: 0.85rem;
    color: #cbd5e1;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    line-height: 1.45;
}

.source-chip a {
    color: #93c5fd;
    word-break: break-all;
}

.web-link-item {
    margin-bottom: 0.65rem;
    padding: 0.55rem 0.75rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
}

.web-link-item a {
    color: #93c5fd;
    text-decoration: none;
    word-break: break-all;
}

.web-link-item a:hover {
    text-decoration: underline;
}

.web-link-snippet {
    color: #94a3b8;
    font-size: 0.82rem;
    margin-top: 0.35rem;
    line-height: 1.4;
}

.step2-empty {
    text-align: center;
    padding: 1.5rem 1rem 1.25rem;
    margin-top: 0.25rem;
}

.step2-empty-icon {
    font-size: 2rem;
    line-height: 1;
    margin-bottom: 0.5rem;
}

.step2-empty-title {
    color: #e2e8f0;
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 0.45rem;
}

.step2-empty-text {
    color: #94a3b8;
    font-size: 0.92rem;
    line-height: 1.5;
    max-width: 34rem;
    margin: 0 auto;
}

.step2-empty-text b {
    color: #cbd5e1;
}

.step2-empty-tags {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.45rem;
    margin-top: 1rem;
}

.step2-tag {
    background: #0f172a;
    border: 1px solid #334155;
    color: #64748b;
    font-size: 0.76rem;
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
}
</style>
"""
