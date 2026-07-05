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
    margin-bottom: 0.85rem;
}

.hero h1 { margin: 0; font-size: 1.55rem; color: #f8fafc; line-height: 1.2; }
.hero-subtitle {
    margin: 0.45rem 0 0;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.45;
    max-width: 52rem;
}

.quick-start {
    background: #172554;
    border: 1px solid #1e40af;
    border-radius: 12px;
    padding: 0.85rem 1rem 1rem;
    margin-bottom: 0.85rem;
}

.quick-start-title {
    color: #bfdbfe;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.65rem;
}

.steps-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.55rem;
}

@media (max-width: 900px) {
    .steps-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 560px) {
    .steps-grid { grid-template-columns: 1fr; }
}

.step-card {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 0.65rem 0.75rem;
    min-height: 4.5rem;
}

.step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.35rem;
    height: 1.35rem;
    border-radius: 999px;
    background: #2563eb;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}

.step-card strong {
    color: #f1f5f9;
    font-size: 0.88rem;
    line-height: 1.3;
}

.step-card span.step-desc {
    display: block;
    color: #94a3b8;
    font-size: 0.8rem;
    line-height: 1.35;
    margin-top: 0.15rem;
}

.mode-banner {
    margin-top: 0.7rem;
    padding: 0.55rem 0.75rem;
    border-radius: 8px;
    font-size: 0.84rem;
    line-height: 1.4;
}

.mode-banner.demo {
    background: #064e3b;
    border: 1px solid #059669;
    color: #a7f3d0;
}

.mode-banner.live {
    background: #1e3a5f;
    border: 1px solid #3b82f6;
    color: #bfdbfe;
}

.generate-panel {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.5rem;
}

.generate-panel-title {
    color: #f1f5f9;
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 0.35rem;
}

.generate-panel-hint {
    color: #94a3b8;
    font-size: 0.84rem;
    line-height: 1.4;
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

.hotspot-grid [data-testid="stDownloadButton"] > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #93c5fd !important;
    font-size: 0.78rem !important;
    font-weight: 400 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.35rem 0 0 !important;
    min-height: 0 !important;
    height: auto !important;
    white-space: normal !important;
    line-height: 1.35 !important;
}

.hotspot-grid [data-testid="stDownloadButton"] > button:hover {
    color: #bfdbfe !important;
    text-decoration: underline !important;
}

.hotspot-grid [data-testid="stDownloadButton"] > button p {
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
}

.hotspot-grid a[data-testid="stLinkButton"],
.hotspot-grid [data-testid="stLinkButton"] > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #93c5fd !important;
    font-size: 0.78rem !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.35rem 0 0 !important;
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

.hypothesis-section {
    margin-top: 0.85rem;
}

.hypothesis-section-heading {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 0.95rem;
    margin: 0 0 0.35rem;
    line-height: 1.4;
}

.hypothesis-section .hypothesis-body {
    margin-bottom: 0.25rem;
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

.novelty-hint {
    display: block;
    margin-top: 0.35rem;
    font-size: 0.86rem;
    line-height: 1.45;
    opacity: 0.92;
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

.source-chip code {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 0.05rem 0.35rem;
    font-size: 0.82rem;
    color: #e2e8f0;
}

.step2-empty {
    background: #1e293b;
    border: 1px dashed #475569;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.5;
    margin-top: 0.5rem;
}

[data-testid="stIFrame"] {
    background: transparent !important;
}

[data-testid="stIFrame"] iframe {
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    background: #1e293b !important;
    display: block;
}

/* «Экспертная настройка»: только label + native (?) без выпадающего списка */
section[data-testid="stSidebar"] div.st-key-expert_settings_hint [data-baseweb="select"] {
    display: none !important;
}
section[data-testid="stSidebar"] div.st-key-expert_settings_hint [data-testid="stSelectbox"] {
    margin-bottom: -0.35rem;
}
</style>
"""
