"""DataLens, the conversational workspace for the BI assistant."""

import logging
from html import escape
from string import punctuation

import httpx
import ollama
import streamlit as st

from config import OLLAMA_HOST, load_semantic_layer
from viz import auto_chart
from workflow import run_pipeline

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

st.set_page_config(
    page_title="DataLens · Intelligent BI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="auto",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700;750;800&display=swap');

:root {
    color-scheme: dark;
    --atlas-bg: #0b0f19;
    --atlas-ink: #f0f3ff;
    --atlas-muted: #a4b0ca;
    --atlas-violet: #b6a6ff;
    --atlas-line: rgba(180, 195, 255, .15);
    --atlas-glass: rgba(255, 255, 255, .035);
}
[data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
    font-family: Inter, system-ui, sans-serif;
    color: var(--atlas-ink);
}
.stApp { background: var(--atlas-bg); color: var(--atlas-ink); }
[data-testid="stMain"] { isolation: isolate; }
[data-testid="stMain"]::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background:
        radial-gradient(ellipse at 69% 14%, #39276b55, transparent 49%),
        radial-gradient(ellipse at 96% 56%, #17385b45, transparent 45%),
        radial-gradient(ellipse at 22% 86%, #1b326338, transparent 51%);
    background-size: 115% 115%;
    animation: atlas-mesh 18s ease-in-out infinite alternate;
}
[data-testid="stMainBlockContainer"],
[data-testid="stBottomBlockContainer"] {
    max-width: 1040px;
    padding-inline: clamp(1rem, 4vw, 3.4rem);
}
[data-testid="stMainBlockContainer"] { padding-top: 3.25rem; padding-bottom: 2rem; }
[data-testid="stHeader"] {
    background: transparent;
    pointer-events: none;
    visibility: hidden;
}
[data-testid="stHeader"] :is([data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] *) {
    pointer-events: auto;
    visibility: visible;
}
[data-testid="stExpandSidebarButton"] {
    border: 1px solid var(--atlas-line);
    border-radius: .6rem;
    background: #171d30;
}
[data-testid="stExpandSidebarButton"] span { color: var(--atlas-violet); }
[data-testid="stSidebarCollapseButton"] { color: var(--atlas-muted); }
[data-testid="stToolbar"]:not(:has([data-testid="stExpandSidebarButton"])),
[data-testid="stStatusWidget"], .stAppDeployButton, #MainMenu, footer {
    display: none !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(155deg, #111728 0%, #0c101c 58%);
    border-right: 1px solid var(--atlas-line);
}
[data-testid="stSidebarUserContent"] { padding-top: .35rem; }
.atlas-overline {
    color: var(--atlas-muted);
    font: 650 .66rem/1.3 Inter, system-ui, sans-serif;
    letter-spacing: .17em;
    text-transform: uppercase;
}
.atlas-sidehead {
    display: flex;
    align-items: center;
    gap: .75rem;
    padding-bottom: .95rem;
    border-bottom: 1px solid var(--atlas-line);
}
.atlas-mark {
    position: relative;
    display: grid;
    width: 2.6rem;
    height: 2.6rem;
    place-items: center;
    border-radius: .85rem;
    color: #e6ddff;
    background: linear-gradient(140deg, #5b42b6, #252755);
    border: 1px solid #af9aff66;
    box-shadow: 0 8px 30px #7e59ff34, inset 0 1px 0 #ffffff29;
    flex: none;
}
.atlas-mark::before {
    content: "";
    width: .85rem;
    aspect-ratio: 1;
    border: 2px solid currentColor;
    border-radius: 50%;
    transform: translate(-.1rem, -.1rem);
    box-shadow: 0 0 10px #c2a5ff70;
}
.atlas-mark::after {
    content: "";
    position: absolute;
    top: 60%;
    left: 54%;
    width: .48rem;
    height: 2px;
    border-radius: 1px;
    background: currentColor;
    transform: rotate(45deg);
}
.atlas-wordmark { font-size: 1.14rem; font-weight: 750; letter-spacing: -.045em; }
.atlas-sidehead .atlas-overline { margin-top: .2rem; font-size: .56rem; }
.atlas-system {
    padding: .78rem .84rem;
    background: var(--atlas-glass);
    border: 1px solid var(--atlas-line);
    border-radius: .85rem;
}
.atlas-status {
    display: flex;
    align-items: center;
    gap: .55rem;
    margin-top: .42rem;
    color: var(--atlas-ink);
    font-size: .83rem;
    font-weight: 550;
}
.atlas-dot {
    width: .48rem;
    height: .48rem;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 10px currentColor;
}
.atlas-online { color: #60edbb; }
.atlas-offline { color: #fbbf7a; }
.atlas-sidebar-title { margin-top: .95rem; }
[data-testid="stMetric"] {
    border: 1px solid var(--atlas-line);
    border-radius: .87rem;
    background: linear-gradient(135deg, #a991ff10, #ffffff04);
    backdrop-filter: blur(10px);
    padding: .73rem .88rem;
    box-shadow: inset 0 1px 0 #ffffff08, 0 7px 18px #06081336;
}
[data-testid="stMetricLabel"] p { color: var(--atlas-muted); font-size: .77rem; }
[data-testid="stMetricValue"] {
    color: var(--atlas-ink);
    font-family: Inter, system-ui, sans-serif;
    font-size: 1.42rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    letter-spacing: -.045em;
}
.st-key-new_analysis button, .st-key-starters button, .st-key-recent_questions button,
[data-testid="stDownloadButton"] button {
    border: 1px solid var(--atlas-line);
    background: #171d30c4;
    color: var(--atlas-ink);
    border-radius: .85rem;
    transition: background .2s ease, border-color .2s ease, transform .2s ease, box-shadow .2s ease;
}
.st-key-new_analysis button { justify-content: flex-start; }
.st-key-new_analysis button:hover, .st-key-recent_questions button:hover,
[data-testid="stDownloadButton"] button:hover {
    border-color: #b6a6ff86;
    color: #f5f0ff;
    background: #272547;
    transform: translateY(-2px);
    box-shadow: 0 9px 22px #05071255;
}
.st-key-new_analysis button:focus-visible, .st-key-starters button:focus-visible,
.st-key-recent_questions button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible,
[data-testid="stChatInput"] button:focus-visible, [data-testid="stExpander"] summary:focus-visible {
    outline: 2px solid var(--atlas-violet);
    outline-offset: 3px;
}
.st-key-recent_questions button {
    justify-content: flex-start;
    text-align: start;
    background: var(--atlas-glass);
}
.st-key-recent_questions button p {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    overflow-wrap: anywhere;
    unicode-bidi: plaintext;
    text-align: start;
    color: var(--atlas-ink);
    font-size: .78rem;
}
.atlas-rail {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: .8rem;
    padding-bottom: .9rem;
    border-bottom: 1px solid var(--atlas-line);
}
.atlas-rail-title {
    display: flex;
    align-items: center;
    gap: .55rem;
    font-size: .88rem;
    font-weight: 650;
}
.atlas-rail-icon { color: var(--atlas-violet); font-size: 1rem; }
.atlas-tag {
    border: 1px solid #a992ff39;
    border-radius: 99px;
    padding: .32rem .62rem;
    background: #9172ff14;
    color: #d3c9ff;
    white-space: nowrap;
    font-size: .66rem;
    font-weight: 650;
}
.atlas-hero {
    position: relative;
    overflow: hidden;
    isolation: isolate;
    padding: clamp(1.5rem, 5vw, 3.6rem);
    border-radius: 1.55rem;
    border: 1px solid #b2a4ff35;
    background:
        radial-gradient(ellipse at 100% 4%, #4f378a75, transparent 64%),
        linear-gradient(136deg, #171b35 0%, #111626 75%);
    box-shadow: inset 0 1px 0 #ffffff12, 0 22px 64px #05071275;
    animation: atlas-in .5s ease-out both;
}
.atlas-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    background-image: radial-gradient(#baafff65 1px, transparent 1px);
    background-size: 18px 18px;
    mask-image: linear-gradient(100deg, transparent 35%, #000 100%);
    opacity: .42;
}
.atlas-orbits {
    position: absolute;
    top: 50%;
    right: -5%;
    width: 48%;
    aspect-ratio: 1.25;
    z-index: -1;
    transform: translateY(-50%) rotate(-22deg);
    pointer-events: none;
    display: grid;
    place-items: center;
    color: #e1d3ff;
    font-size: 2.2rem;
    text-shadow: 0 0 20px #bd9cff;
    background: radial-gradient(ellipse at center, #a987ff38, transparent 26%);
}
.atlas-orbits::before, .atlas-orbits::after {
    content: "";
    position: absolute;
    border: 1px solid #bb9cff75;
    border-radius: 50%;
    box-shadow: 0 0 22px #947aff1c, inset 0 0 22px #947aff1c;
}
.atlas-orbits::before { inset: 27% 9%; }
.atlas-orbits::after { inset: 14% 1%; opacity: .56; }
.atlas-hero .atlas-overline { color: #cabaff; }
.atlas-hero h1 {
    margin: .7rem 0 .8rem;
    padding: 0;
    color: var(--atlas-ink);
    font: 750 clamp(2.4rem, 6vw, 4.25rem)/1.05 Inter, system-ui, sans-serif;
    letter-spacing: -.075em;
}
.atlas-hero h1 span {
    color: #c9baff;
    background: linear-gradient(105deg, #dfd4ff, #a88eff 65%, #95caff);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
.atlas-hero p {
    max-width: 31rem;
    margin: 0;
    color: #bac5e0;
    font-size: clamp(.88rem, 2vw, 1rem);
    line-height: 1.65;
}
.atlas-starters-title { margin: .75rem 0 .1rem; }
.st-key-starters button {
    min-height: 5.3rem;
    padding: .85rem;
    justify-content: flex-start;
    text-align: left;
    background: var(--atlas-glass);
    backdrop-filter: blur(10px);
}
.st-key-starters button p { color: inherit; font-size: .83rem; text-align: left; }
.st-key-starters button [data-testid="stIconMaterial"] { color: var(--atlas-violet); }
.st-key-starters button:hover {
    border-color: #bc9bffe6;
    background: #292247;
    color: #f5f0ff;
    transform: translateY(-3px) scale(1.025);
    box-shadow: 0 0 22px #aa7bff4d, 0 9px 22px #05071255;
}
.atlas-hint { color: var(--atlas-muted); font-size: .75rem; }
[data-testid="stChatMessage"] {
    border: 1px solid var(--atlas-line);
    border-radius: 1.15rem;
    background: var(--atlas-glass);
    backdrop-filter: blur(10px);
    padding: clamp(.75rem, 2.5vw, 1.2rem);
    box-shadow: inset 0 1px 0 #ffffff0b, 0 14px 36px #0507123d;
    animation: atlas-in .36s cubic-bezier(.2, .7, .3, 1) both;
}
[class*="st-key-user_turn_"] [data-testid="stChatMessage"] {
    margin-inline-start: auto;
    width: fit-content;
    max-width: 88%;
    background: linear-gradient(135deg, #7b5aec26, #4460b51e);
    border-color: #ae9bff42;
}
[data-testid="stChatMessageContent"] { min-width: 0; }
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] {
    background: #2b234e;
    color: #ddcfff;
    border: 1px solid #ba9cff45;
}
[class*="st-key-user_turn_"] [data-testid="stChatMessageAvatarCustom"] {
    background: #222e51;
    color: #c7d9ff;
}
.atlas-message {
    color: var(--atlas-ink);
    font-size: .94rem;
    line-height: 1.65;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}
.atlas-message-title {
    margin-bottom: .23rem;
    color: var(--atlas-violet);
    font-size: .71rem;
    font-weight: 700;
}
.atlas-error .atlas-message-title { color: #ffb5c3; }
.atlas-result-label {
    color: var(--atlas-muted);
    font-size: .71rem;
    font-weight: 650;
    letter-spacing: .11em;
    text-transform: uppercase;
}
[data-testid="stExpander"] details {
    border: 1px solid var(--atlas-line);
    border-radius: .76rem;
    background: #090d17a3;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p { color: #dbe3f9; }
[data-testid="stExpander"] summary:hover { color: var(--atlas-violet); }
[data-testid="stCode"] pre {
    background: #070b14 !important;
    border: 1px solid #9e87ff39;
    border-radius: .65rem;
}
[data-testid="stCode"] pre code { color: #dce5ff !important; font-size: .83rem; }
[data-testid="stCode"] :is(.keyword, .operator, .hljs-keyword, .hljs-operator) { color: #c9a7ff !important; }
[data-testid="stCode"] :is(.string, .literal, .hljs-string, .hljs-literal) { color: #7de4c3 !important; }
[data-testid="stCode"] :is(.number, .function, .hljs-number, .hljs-built_in) { color: #ffcb94 !important; }
[data-testid="stPlotlyChart"] {
    border: 1px solid var(--atlas-line);
    border-radius: .85rem;
    background: #070c1870;
    animation: atlas-in .45s .09s ease-out both;
}
[data-testid="stBottom"], [data-testid="stBottom"] > div {
    background: transparent;
}
[data-testid="stBottomBlockContainer"] {
    padding-top: .55rem;
    padding-bottom: 1rem;
    background: linear-gradient(0deg, #0b0f19 66%, #0b0f1900);
}
[data-testid="stChatInput"] {
    border: 1px solid #aa95ff5c;
    border-radius: 1rem;
    background: #171e33f2;
    box-shadow: 0 12px 36px #04050d9c, inset 0 1px 0 #ffffff12;
    transition: border-color .2s ease, box-shadow .2s ease;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #b6a6ff;
    box-shadow: 0 0 0 3px #a18aff29, 0 12px 36px #04050d9c;
}
[data-testid="stChatInput"] :is(textarea, [data-baseweb="textarea"], [data-baseweb="base-input"]) {
    background: transparent;
    color: var(--atlas-ink);
    font-family: Inter, system-ui, sans-serif;
}
[data-testid="stChatInput"] textarea::placeholder { color: #a7b1c9; opacity: 1; }
[data-testid="stChatInput"] button {
    color: #f5f0ff;
    background: #6549bf;
    border-radius: .65rem;
}
[data-testid="stChatInput"] button:disabled { background: #343356; color: #b2abce; }
[data-testid="stChatInput"] button:not(:disabled):hover { background: #765bd2; }
[data-testid="stCaptionContainer"] p, [data-testid="stSpinner"] p { color: var(--atlas-muted); }

@keyframes atlas-in {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes atlas-mesh {
    from { background-position: 0% 0%; }
    to { background-position: 100% 100%; }
}
@media (max-width: 680px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3rem; }
    .atlas-orbits { width: 77%; right: -23%; opacity: .35; }
    .st-key-starters [data-testid="stHorizontalBlock"] { flex-direction: column; }
    .st-key-starters [data-testid="stColumn"] { width: 100%; flex: 1 1 auto; }
    .st-key-starters button { min-height: 3.4rem; }
    [class*="st-key-user_turn_"] [data-testid="stChatMessage"] { max-width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""

BRAND = """
<div class="atlas-sidehead">
  <div class="atlas-mark" aria-hidden="true"></div>
  <div><div class="atlas-wordmark">DataLens</div><div class="atlas-overline">Intelligent BI</div></div>
</div>
"""

HERO = """
<section class="atlas-hero" aria-labelledby="atlas-title">
  <div class="atlas-orbits" aria-hidden="true">✦</div>
  <div class="atlas-overline">Vos données ERP &amp; CRM</div>
  <h1 id="atlas-title">Vos données.<br><span>Vos réponses.</span></h1>
  <p>Posez une question en français ou en arabe. Explorez les résultats avec un graphique
     interactif, une synthèse et la requête SQL qui les a produits.</p>
</section>
"""

STARTERS = (
    (":material/monitoring:", "Chiffre d’affaires par filiale",
     "Quel est le chiffre d’affaires TTC par filiale active cette année ?"),
    (":material/inventory_2:", "Produits en alerte de stock",
     "Quels produits actifs sont au seuil d’alerte ou en dessous dans les filiales actives ?"),
    (":material/receipt_long:", "الفواتير المدفوعة حسب الشهر",
     "كم عدد الفواتير المدفوعة في كل شهر؟"),
)
HISTORY_LABEL_ESCAPES = str.maketrans({char: f"\\{char}" for char in punctuation})


@st.cache_data
def semantic_layer():
    return load_semantic_layer()


@st.cache_data(ttl=30, show_spinner=False)
def ollama_connected(host):
    try:
        ollama.Client(host=host, timeout=1.5).list()
    except (ConnectionError, ollama.ResponseError, httpx.RequestError):
        return False
    return True


def new_analysis():
    for index in range(len(st.session_state.get("atlas_history", []))):
        st.session_state.pop(f"atlas_feedback_{index}", None)
    st.session_state["atlas_history"] = []
    st.session_state.pop("atlas_suggestion", None)


def choose_question(question):
    st.session_state["atlas_suggestion"] = question


def render_recent_questions(questions):
    with st.container(key="recent_questions"):
        st.html('<div class="atlas-overline atlas-sidebar-title">🕒 Historique</div>')
        if not questions:
            st.caption("Aucune question dans cette session.")
        for index, question in enumerate(questions):
            label = " ".join(question.split()).translate(HISTORY_LABEL_ESCAPES)
            st.button(
                label, key=f"atlas_recent_{index}", width="stretch", wrap=True,
                on_click=choose_question, args=(question,),
            )


def record_feedback(index):
    vote = st.session_state[f"atlas_feedback_{index}"]
    if vote is not None:
        LOGGER.info("feedback=%s turn=%d", "up" if vote == 1 else "down", index + 1)


def render_metrics(slot, result):
    with slot.container():
        st.html('<div class="atlas-overline atlas-sidebar-title">Performances</div>')
        st.caption("Dernière analyse" if result else "En attente d’une première question")
        for label, field in (
            ("Génération SQL", "generation_seconds"),
            ("Exécution SQL", "execution_seconds"),
            ("Latence totale", "total_seconds"),
        ):
            value = f"{getattr(result, field):.3f} s" if result else "—"
            st.metric(label, value)
        if result and result.retries:
            st.caption(f"Corrections SQL tentées · {result.retries}")


def render_user(question, index):
    with st.container(key=f"user_turn_{index}"), st.chat_message("user", avatar=":material/person:"):
        st.html(f'<div class="atlas-message" dir="auto">{escape(question)}</div>')


def render_result(result, index):
    if result.error:
        st.html(
            '<div class="atlas-error"><div class="atlas-message-title">Analyse interrompue</div>'
            f'<div class="atlas-message" dir="auto">{escape(result.error)}</div></div>'
        )
    else:
        st.html(
            '<div class="atlas-message-title">Synthèse</div>'
            f'<div class="atlas-message" dir="auto">{escape(result.explanation)}</div>'
        )
        frame = result.dataframe
        if frame.empty:
            st.caption("Aucune donnée ne correspond à la question.")
        else:
            figure = auto_chart(frame)
            if figure is not None:
                figure.update_layout(
                    template="plotly_dark",
                    height=340,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"family": "Inter, system-ui, sans-serif", "color": "#cdd7ef"},
                    margin={"l": 30, "r": 22, "t": 50 if figure.layout.title.text else 24, "b": 26},
                    hoverlabel={"bgcolor": "#171e33", "bordercolor": "#6857a7"},
                )
                figure.update_xaxes(gridcolor="rgba(180,195,255,.11)", zerolinecolor="rgba(180,195,255,.18)")
                figure.update_yaxes(gridcolor="rgba(180,195,255,.11)", zerolinecolor="rgba(180,195,255,.18)")
                st.plotly_chart(figure, theme=None, width="stretch", key=f"atlas_chart_{index}",
                                config={"displaylogo": False, "responsive": True})
        row_count = len(frame)
        rows = "ligne" if row_count == 1 else "lignes"
        st.html(f'<div class="atlas-result-label">Données · {row_count} {rows}</div>')
        st.dataframe(frame, width="stretch", hide_index=True)
        st.download_button(
            "📥 Exporter en CSV",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name=f"datalens-analyse-{index + 1}.csv",
            mime="text/csv; charset=utf-8",
            key=f"atlas_csv_{index}",
            on_click="ignore",
        )

    if result.sql:
        with st.expander("Requête SQL", icon=":material/terminal:"):
            st.code(result.sql, language="sql", line_numbers=True, wrap_lines=True)

    if not result.error:
        st.caption("Cette analyse vous a-t-elle aidé ?")
        vote = st.feedback(
            "thumbs", key=f"atlas_feedback_{index}", on_change=record_feedback, args=(index,)
        )
        if vote is not None:
            st.caption("Merci pour votre retour.")


def render_welcome():
    st.html(HERO)
    with st.container(key="starters"):
        st.html('<div class="atlas-overline atlas-starters-title">Premières explorations</div>')
        columns = st.columns(len(STARTERS))
        for index, (icon, label, question) in enumerate(STARTERS):
            with columns[index]:
                st.button(
                    label, icon=icon, width="stretch", wrap=True,
                    key=f"atlas_starter_{index}", on_click=choose_question, args=(question,),
                )


st.html(CSS)
history = st.session_state.setdefault("atlas_history", [])
recent_questions = st.session_state.setdefault("atlas_recent_questions", [])
suggested = st.session_state.pop("atlas_suggestion", "")
clear_composer = st.session_state.pop("atlas_clear_composer", False)
if suggested or clear_composer:
    st.session_state["atlas_composer"] = suggested
typed = st.chat_input(
    "Posez votre question… / اطرح سؤالك", key="atlas_composer",
    max_chars=1500, disabled=bool(suggested),
)
question = (suggested or typed or "").strip()
if question:
    recent_questions.insert(0, question)
    del recent_questions[3:]

with st.sidebar:
    st.html(BRAND)
    connected = ollama_connected(OLLAMA_HOST)
    status_class = "atlas-online" if connected else "atlas-offline"
    status_text = "Ollama connecté" if connected else "Ollama indisponible"
    st.html(
        '<div class="atlas-system" role="status">'
        '<div class="atlas-overline">État du système</div>'
        f'<div class="atlas-status"><span class="atlas-dot {status_class}" aria-hidden="true"></span>'
        f'{status_text}</div></div>'
    )
    st.button("Nouvelle analyse", key="new_analysis", icon=":material/add:",
              width="stretch", on_click=new_analysis)
    metrics_slot = st.empty()
    render_metrics(metrics_slot, history[-1][1] if history else None)
    render_recent_questions(recent_questions)
    st.html('<div class="atlas-hint">PostgreSQL · Lecture seule</div>')

st.html("""
<div class="atlas-rail">
  <div class="atlas-rail-title"><span class="atlas-rail-icon" aria-hidden="true">✦</span> Espace d’analyse</div>
  <span class="atlas-tag">FR · العربية</span>
</div>
""")
if not history and not question:
    render_welcome()

for index, (previous_question, result) in enumerate(history):
    render_user(previous_question, index)
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        render_result(result, index)

if question:
    index = len(history)
    render_user(question, index)
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        with st.spinner("DataLens analyse vos données…"):
            result = run_pipeline(question, semantic_layer())
        history.append((question, result))
        if suggested:
            st.session_state["atlas_clear_composer"] = True
            st.rerun()
        render_result(result, index)
    render_metrics(metrics_slot, result)
