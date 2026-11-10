"""Тема и стили интерфейса.

Палитры задаются CSS-переменными: тёмная — по умолчанию, светлая включается
переключателем (параметр ?theme=light в URL) или нативным выбором темы
Streamlit в меню Settings (приложение подхватывает её автоматически через
st.context.theme.type).
"""

from __future__ import annotations

import html as html_lib
import re

import streamlit as st

from app.config import get_config

DARK_VARS = """
.stApp {
  --bg:#0F1117; --surface:#151A23; --surface2:#1B2130;
  --border:#232B3B; --border-strong:#2E3850;
  --text:#E8EBF4; --text-dim:#C3CAD9; --muted:#97A0B5;
  --accent:#7C8CFF; --accent-hover:#93A1FF; --accent-press:#6674EE;
  --accent-soft:rgba(124,140,255,.13);
  --success:#43D9A3; --warning:#F5B84C; --danger:#F1707B;
  --success-bg:rgba(67,217,163,.12); --warning-bg:rgba(245,184,76,.12);
  --danger-bg:rgba(241,112,123,.14);
  --shadow-rest:0 1px 3px rgba(0,0,0,.12);
  --shadow-hover:0 10px 30px rgba(0,0,0,.38);
  --shadow:var(--shadow-hover);
  --focus-ring:0 0 0 2px color-mix(in srgb, var(--accent) 55%, transparent),
               0 0 0 5px color-mix(in srgb, var(--accent) 20%, transparent);
  --glass:rgba(17,21,30,.74);
  --tone0-bg:rgba(124,140,255,.16); --tone0-fg:#A5B0FF;
  --tone1-bg:rgba(61,214,170,.15);  --tone1-fg:#5CE0BC;
  --tone2-bg:rgba(245,184,76,.15);  --tone2-fg:#F6C36B;
  --tone3-bg:rgba(241,112,123,.15); --tone3-fg:#F58B94;
  --tone4-bg:rgba(96,190,255,.15);  --tone4-fg:#7CC5FF;
  --tone5-bg:rgba(192,132,252,.15); --tone5-fg:#CE9EFC;
  --tone6-bg:rgba(163,214,110,.15); --tone6-fg:#B4DE7E;
  --tone7-bg:rgba(148,163,184,.15); --tone7-fg:#AEB9CC;
}
"""

LIGHT_VARS = """
.stApp {
  --bg:#F3F5FA; --surface:#FFFFFF; --surface2:#EEF1F8;
  --border:#E2E7F1; --border-strong:#CBD4E6;
  --text:#171D2B; --text-dim:#3E4863; --muted:#5A6580;
  --accent:#5B6BF0; --accent-hover:#6E7CF3; --accent-press:#4C5BE0;
  --accent-soft:rgba(91,107,240,.10);
  --success:#149E6E; --warning:#C77E12; --danger:#D6455C;
  --success-bg:rgba(20,158,110,.10); --warning-bg:rgba(199,126,18,.10);
  --danger-bg:rgba(214,69,92,.10);
  --shadow-rest:0 1px 3px rgba(23,29,43,.08);
  --shadow-hover:0 10px 30px rgba(23,29,43,.12);
  --shadow:var(--shadow-hover);
  --focus-ring:0 0 0 2px color-mix(in srgb, var(--accent) 55%, transparent),
               0 0 0 5px color-mix(in srgb, var(--accent) 18%, transparent);
  --glass:rgba(255,255,255,.78);
  --tone0-bg:rgba(91,107,240,.10);  --tone0-fg:#4353D6;
  --tone1-bg:rgba(20,158,110,.10);  --tone1-fg:#0C7D57;
  --tone2-bg:rgba(199,126,18,.10);  --tone2-fg:#96620D;
  --tone3-bg:rgba(214,69,92,.10);   --tone3-fg:#B3324A;
  --tone4-bg:rgba(0,134,201,.10);   --tone4-fg:#046EA6;
  --tone5-bg:rgba(105,56,239,.10);  --tone5-fg:#5B2BC4;
  --tone6-bg:rgba(63,122,11,.10);   --tone6-fg:#3F7A0B;
  --tone7-bg:rgba(71,84,103,.10);   --tone7-fg:#475467;
}
"""

CSS_TEMPLATE = """
__VARS__

/* ── База и типографика ─────────────────────────────────────────────── */
.stApp {
  background: var(--bg);
  color: var(--text);
  font-family: "Inter", "SF Pro Text", "Segoe UI", system-ui, -apple-system,
    "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.block-container { max-width: 1160px; padding: 1.4rem 1.3rem 4rem; }

h1 {
  font-size: clamp(1.45rem, 1.2rem + 0.9vw, 1.8rem) !important;
  font-weight: 750 !important;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
h2 {
  font-size: clamp(1.08rem, 1rem + 0.35vw, 1.24rem) !important;
  font-weight: 700 !important;
  letter-spacing: -0.01em;
  line-height: 1.15;
}
h3 { font-size: 1rem !important; font-weight: 650 !important; line-height: 1.15; }
h1, h2, h3 { color: var(--text); }

[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
  color: var(--text-dim);
  line-height: 1.55;
}
[data-testid="stMarkdownContainer"] b, [data-testid="stMarkdownContainer"] strong {
  color: var(--text);
}
a { color: var(--accent); }

[data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] p {
  color: var(--muted) !important;
}
[data-testid="stWidgetLabel"] p { font-size: .86rem; }

.stat-num, .stat-label, .qty-display, .badge, .badge-plain,
td, [data-testid="stMetricValue"] {
  font-variant-numeric: tabular-nums;
}

header[data-testid="stHeader"] { background: transparent; }
[data-testid="stStatusWidget"] { opacity: .6; }

/* ── Фокус-кольца (клавиатурная навигация) ─────────────────────────── */
[data-testid^="stBaseButton-"]:focus-visible,
[data-testid="stFormSubmitButton"] button:focus-visible,
[data-testid="stDownloadButton"] button:focus-visible,
[data-testid="stTextInput"] input:focus-visible,
[data-testid="stNumberInput"] input:focus-visible,
[data-testid="stTextArea"] textarea:focus-visible,
[data-baseweb="select"] > div:focus-within {
  outline: none;
  box-shadow: var(--focus-ring) !important;
}
a:focus-visible,
[data-testid="stSidebar"] a:focus-visible {
  outline: none;
  border-radius: 6px;
  box-shadow: var(--focus-ring);
}

/* ── Боковая панель: стекло ─────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--glass) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] a {
  color: var(--text-dim);
  border-radius: 10px;
  transition: background-color .16s ease, color .16s ease;
}
[data-testid="stSidebar"] a:hover { background: var(--surface2); color: var(--text); }
[data-testid="stSidebar"] a[aria-current="page"],
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
  font-weight: 650;
}
.side-section {
  font-size: .72rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted); margin: .2rem 0 .4rem;
}

/* ── Кнопки ─────────────────────────────────────────────────────────── */
[data-testid^="stBaseButton-"], [data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button {
  border-radius: 10px;
  font-weight: 600;
  transition: background-color .16s ease, border-color .16s ease,
    box-shadow .16s ease, transform .16s ease, color .16s ease;
}
[data-testid="stBaseButton-primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background: var(--accent);
  border: 1px solid transparent;
  color: #fff;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background: var(--accent-hover);
  box-shadow: 0 4px 16px color-mix(in srgb, var(--accent) 40%, transparent);
}
[data-testid="stBaseButton-primary"]:active,
[data-testid="stFormSubmitButton"] button[kind="primary"]:active {
  background: var(--accent-press);
  transform: translateY(1px);
}
[data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
  background: transparent;
  border: 1px solid var(--border-strong);
  color: var(--text);
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
  background: var(--surface2);
  border-color: var(--accent);
  color: var(--text);
}
[data-testid="stBaseButton-tertiary"], [data-testid="stBaseButton-borderless"] {
  color: var(--text-dim);
}
[data-testid="stBaseButton-tertiary"]:hover, [data-testid="stBaseButton-borderless"]:hover {
  background: var(--surface2);
  color: var(--text);
}

/* Явно выключенные кнопки (например, «−» при нулевом количестве):
   без transform, теней и hover-подсветки. */
[data-testid^="stBaseButton-"]:disabled,
[data-testid="stFormSubmitButton"] button:disabled,
[data-testid="stDownloadButton"] button:disabled {
  opacity: .5;
  transform: none !important;
  box-shadow: none !important;
  cursor: not-allowed;
}

/* ── Поля ввода ─────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  transition: border-color .16s ease, box-shadow .16s ease;
}
[data-testid="stTextInput"] input:hover:not(:focus),
[data-testid="stNumberInput"] input:hover:not(:focus),
[data-testid="stTextArea"] textarea:hover:not(:focus),
[data-testid="stDateInput"] input:hover:not(:focus) {
  border-color: var(--border-strong);
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stDateInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent) !important;
  color: var(--text);
}
[data-testid="stNumberInput"] button {
  background: var(--surface2);
  color: var(--text-dim);
  border-color: var(--border);
}
[data-baseweb="select"] > div {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  transition: border-color .16s ease, box-shadow .16s ease;
  min-height: 2.4em;
  overflow: hidden;
}
[data-baseweb="select"] > div:hover { border-color: var(--border-strong); }
[data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent) !important;
}
[data-baseweb="select"] svg { fill: var(--muted); }
[data-baseweb="select"] input { color: var(--text); }
[data-baseweb="popover"] > div {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: border-color .16s ease;
}
[data-baseweb="popover"] li:hover { background: color-mix(in srgb, var(--accent) 14%, transparent); }

[data-testid="stCheckbox"] { color: var(--text-dim); }

/* ── Экспандеры, поповеры, формы ────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--surface);
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  overflow: hidden;
  transition: border-color .16s ease, box-shadow .16s ease;
}
[data-testid="stExpander"]:hover { border-color: var(--border-strong) !important; }
[data-testid="stExpander"] details {
  background: transparent !important;
  border: none !important;
}
[data-testid="stExpander"] summary { transition: color .16s ease; }
[data-testid="stExpander"] summary:hover { color: var(--accent); }

[data-testid="stPopoverBody"] {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: border-color .16s ease;
}

[data-testid="stForm"] { border: none; padding: 0; }

[data-testid="stSegmentedControl"] {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 3px;
  transition: border-color .16s ease;
}
[data-testid="stSegmentedControl"] button { border-radius: 9px; color: var(--text-dim); }
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
  background: var(--accent);
  color: #fff;
}

/* ── Карточки-контейнеры (st.container(border=True, key="...")) ─────── */
[class*="st-key-"][class*="itemcard"], [class*="st-key-"][class*="boxcard"],
[class*="st-key-"][class*="loccard"], [class*="st-key-"][class*="info_card"],
[class*="st-key-"][class*="qr_card"], [class*="st-key-"][class*="qty_card"] {
  background: var(--surface);
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  padding: 1rem 1.1rem;
  box-shadow: var(--shadow-rest);
  transition: border-color .16s ease, box-shadow .16s ease;
}
[class*="st-key-"][class*="itemcard"]:hover, [class*="st-key-"][class*="boxcard"]:hover,
[class*="st-key-"][class*="loccard"]:hover {
  border-color: var(--border-strong) !important;
  box-shadow: var(--shadow-hover);
}

/* Степпер количества и кнопки карточек: зона тапа 44px. */
[class*="st-key-"][class*="itemcard"] [data-testid^="stBaseButton-"],
[class*="st-key-"][class*="itemcard"] [data-testid="stPopover"] > button {
  min-width: 44px;
}

/* ── Полоса отмены удаления (единый вид на всех страницах) ──────────── */
.st-key-undo_strip {
  background: var(--danger-bg) !important;
  border: 1px solid color-mix(in srgb, var(--danger) 38%, transparent) !important;
  border-radius: 12px !important;
  padding: .55rem .8rem !important;
  animation: slide-down .24s ease-out both;
}
.st-key-undo_strip .item-meta { color: var(--text-dim); }

/* ── Таблицы, алерты, код ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--shadow-rest);
}
[data-testid="stAlert"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border);
  border-radius: 12px;
}
[data-testid="stAlert"] * { color: var(--text-dim); }
[data-testid="stCode"] {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
}
[data-testid="stCode"] pre, [data-testid="stCode"] code { color: var(--text-dim) !important; }
[data-testid="stDivider"] hr { border-color: var(--border); }
[data-testid="stImage"] img { border-radius: 10px; }

/* ── Кастомные элементы ─────────────────────────────────────────────── */
.brand { display: flex; gap: 11px; align-items: center; padding: .3rem .15rem .7rem; }
.brand-logo {
  width: 38px; height: 38px; border-radius: 11px; flex: none;
  background: linear-gradient(135deg, var(--accent), #9F6CFF);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 45%, transparent);
}
.brand-name { font-weight: 750; font-size: 1rem; color: var(--text); line-height: 1.15; }
.brand-sub { font-size: .73rem; color: var(--muted); }

/* ── Анимации появления ─────────────────────────────────────────────── */
@keyframes rise-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slide-down {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes breathe {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.05); opacity: .85; }
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
  gap: 13px;
  margin: .4rem 0 1rem;
}
.stat-card {
  display: flex; gap: 13px; align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 15px 17px;
  box-shadow: var(--shadow-rest);
  animation: rise-in .24s ease-out both;
  transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}
.stat-card:nth-child(2) { animation-delay: .04s; }
.stat-card:nth-child(3) { animation-delay: .08s; }
.stat-card:nth-child(4) { animation-delay: .12s; }
.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-hover);
}
.stat-icon {
  width: 42px; height: 42px; border-radius: 12px; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 21px;
  background: var(--accent-soft);
}
.stat-num { font-size: 1.55rem; font-weight: 750; line-height: 1.1; color: var(--text); }
.stat-label {
  font-size: .72rem; color: var(--muted); margin-top: 3px;
  text-transform: uppercase; letter-spacing: .06em;
}

.badge {
  display: inline-flex; align-items: center;
  padding: 2px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 650; line-height: 1.5;
  margin-right: 6px; vertical-align: middle;
}
.badge.tone-0 { background: var(--tone0-bg); color: var(--tone0-fg); border: 1px solid color-mix(in srgb, var(--tone0-fg) 30%, transparent); }
.badge.tone-1 { background: var(--tone1-bg); color: var(--tone1-fg); border: 1px solid color-mix(in srgb, var(--tone1-fg) 30%, transparent); }
.badge.tone-2 { background: var(--tone2-bg); color: var(--tone2-fg); border: 1px solid color-mix(in srgb, var(--tone2-fg) 30%, transparent); }
.badge.tone-3 { background: var(--tone3-bg); color: var(--tone3-fg); border: 1px solid color-mix(in srgb, var(--tone3-fg) 30%, transparent); }
.badge.tone-4 { background: var(--tone4-bg); color: var(--tone4-fg); border: 1px solid color-mix(in srgb, var(--tone4-fg) 30%, transparent); }
.badge.tone-5 { background: var(--tone5-bg); color: var(--tone5-fg); border: 1px solid color-mix(in srgb, var(--tone5-fg) 30%, transparent); }
.badge.tone-6 { background: var(--tone6-bg); color: var(--tone6-fg); border: 1px solid color-mix(in srgb, var(--tone6-fg) 30%, transparent); }
.badge.tone-7 { background: var(--tone7-bg); color: var(--tone7-fg); border: 1px solid color-mix(in srgb, var(--tone7-fg) 30%, transparent); }
.badge-plain {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 10px; border-radius: 999px;
  font-size: .74rem; font-weight: 600;
  background: var(--surface2); color: var(--text-dim);
  border: 1px solid var(--border);
  margin-right: 6px; vertical-align: middle;
}

.item-name { font-weight: 650; font-size: .98rem; color: var(--text); line-height: 1.35; }
.item-meta { color: var(--muted); font-size: .8rem; margin-top: 3px; }
.qty-display {
  font-weight: 750; font-size: 1.02rem; text-align: center;
  color: var(--text); min-width: 2em;
}
.section-title {
  font-size: 1.02rem; font-weight: 700; color: var(--text);
  margin: 1.25rem 0 .35rem;
}

/* ── Пустые состояния ───────────────────────────────────────────────── */
.empty-state { text-align: center; padding: 2.4rem 1rem 1.6rem; }
.empty-icon {
  font-size: 2.5rem; margin-bottom: .5rem;
  width: 74px; height: 74px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface2); border: 1px solid var(--border);
  margin-left: auto; margin-right: auto;
  animation: breathe 3.2s ease-in-out infinite;
}
.empty-title { font-size: 1.05rem; font-weight: 700; color: var(--text); margin-bottom: .25rem; }
.empty-hint { font-size: .88rem; color: var(--muted); }

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }

/* ── Адаптивность ───────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .block-container { padding: 1rem .85rem 3rem; }
  h1 { font-size: clamp(1.3rem, 1.15rem + 0.8vw, 1.5rem) !important; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .stat-card { padding: 12px 14px; animation: none; }
  .stat-num { font-size: 1.3rem; }
  [data-testid="stVerticalBlockBorderWrapper"] { padding: .8rem .9rem; }
  /* Колонки остаются в одну строку на узких экранах — Streamlit по
     умолчанию складывает их вертикально, что ломает карточки вещей
     и степперы количества. */
  [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
  [data-testid="stColumn"] { min-width: 0 !important; }
  /* Исключение: карточка ящика складывается — информация сверху,
     QR-блок под ней. */
  .st-key-box_info_card [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  .st-key-box_info_card [data-testid="stColumn"] {
    flex: 1 1 100% !important; width: 100% !important;
  }
  [data-testid="stImage"] img { max-width: 100%; height: auto; }
}

/* ── Доступность: уважаем системную настройку «меньше движения» ─────── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}
"""


def resolve_theme() -> str:
    """Активная тема: сначала явный выбор (?theme=), затем тема из Streamlit.

    st.context.theme.type отражает тему, выбранную пользователем в меню
    Settings (Light/Dark); при первом рендере он может быть None — тогда
    считаем тёмную тему (она по умолчанию).
    """
    qp = st.query_params.get("theme")
    if qp in ("dark", "light"):
        return qp
    try:
        detected = st.context.theme.type  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — context недоступен вне рантайма
        detected = None
    return detected if detected in ("dark", "light") else "dark"


def inject_css() -> str:
    """Подключает палитру активной темы и возвращает её имя."""
    theme = resolve_theme()
    css = CSS_TEMPLATE.replace("__VARS__", DARK_VARS if theme == "dark" else LIGHT_VARS)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    return theme


def brand_html() -> None:
    name = re.sub(r"^[^\w\u0400-\u04FF]+", "", get_config().app_title).strip() or "Домашний склад"
    st.markdown(
        '<div class="brand"><div class="brand-logo">📦</div>'
        f"<div><div class=\"brand-name\">{html_lib.escape(name)}</div>"
        '<div class="brand-sub">учёт вещей в ящиках</div></div></div>',
        unsafe_allow_html=True,
    )


def theme_toggle(theme: str) -> None:
    """Переключатель светлой/тёмной темы. Выбор сохраняется в URL (?theme=),
    поэтому переживает перезагрузку страницы; кроме того, приложение следует
    теме из меню Settings Streamlit, если явный параметр не задан."""
    label = "☀️ Светлая тема" if theme == "dark" else "🌙 Тёмная тема"
    if st.button(label, use_container_width=True, key="theme_toggle_btn"):
        st.query_params["theme"] = "light" if theme == "dark" else "dark"
        st.rerun()
