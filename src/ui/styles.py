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
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.75rem;
}

.hero h1 { margin: 0; font-size: 1.45rem; color: #f8fafc; line-height: 1.2; }
.hero p { margin: 0.35rem 0 0; color: #94a3b8; font-size: 0.85rem; line-height: 1.35; }

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
}

.statement-box {
    background: #0f172a;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    color: #e2e8f0;
    font-style: italic;
    border-left: 3px solid #6366f1;
    margin-bottom: 1rem;
}

.novelty-new {
    background: #064e3b;
    border: 1px solid #059669;
    border-radius: 8px;
    padding: 0.65rem 0.85rem;
    color: #a7f3d0;
    font-size: 0.9rem;
}

.novelty-known {
    background: #451a03;
    border: 1px solid #d97706;
    border-radius: 8px;
    padding: 0.65rem 0.85rem;
    color: #fde68a;
    font-size: 0.9rem;
}

.source-chip {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.4rem;
    font-size: 0.85rem;
    color: #cbd5e1;
}

.mode-demo { color: #34d399; font-weight: 600; }
.mode-live { color: #60a5fa; font-weight: 600; }

.howto {
    background: #172554;
    border: 1px solid #1e40af;
    border-radius: 8px;
    padding: 0.65rem 1rem;
    color: #bfdbfe;
    font-size: 0.88rem;
    margin-bottom: 0.75rem;
    line-height: 1.45;
}

footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
"""
