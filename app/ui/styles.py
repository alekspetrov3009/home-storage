"""Тема и стили интерфейса: calm dashboard (эстетика Linear/Notion/Vercel).

Палитры задаются CSS-переменными: тёмная — по умолчанию, светлая включается
переключателем (параметр ?theme=light в URL) или нативным выбором темы
Streamlit в меню Settings (приложение подхватывает её автоматически через
st.context.theme.type).

Дизайн-система: нейтральные цинковые поверхности без синевы, мягкая глубина
(тени) вместо рамок, приглушённый индиго-акцент, типографика как каркас
(h1-display, caps-оверлайны, tabular-nums). Кастомные элементы: bento-сетка
статистики, hero-шапки страниц, чипы и pill-кнопки.
"""

from __future__ import annotations

import html as html_lib
import re

import streamlit as st

from app.config import get_config

DARK_VARS = """
.stApp {
  --bg:#0E0F13; --surface:#16171C; --surface2:#1D1F26;
  --border:#26282F; --border-strong:#33363F;
  --text:#EDEEF2; --text-dim:#B6BAC6; --muted:#8C91A1;
  --accent:#7D85EC; --accent-hover:#9097F1; --accent-press:#6A72DD;
  --accent-soft:rgba(125,133,236,.13);
  --success:#3FC79B; --warning:#E4B05C; --danger:#E57882;
  --success-bg:rgba(63,199,155,.12); --warning-bg:rgba(228,176,92,.12);
  --danger-bg:rgba(229,120,130,.14);
  --shadow-rest:0 1px 2px rgba(0,0,0,.22);
  --shadow-hover:0 8px 28px rgba(0,0,0,.34);
  --shadow:var(--shadow-hover);
  --focus-ring:0 0 0 2px color-mix(in srgb, var(--accent) 55%, transparent),
               0 0 0 5px color-mix(in srgb, var(--accent) 20%, transparent);
  --glass:rgba(14,15,19,.76);
  --tone0-bg:rgba(125,133,236,.16); --tone0-fg:#9BA5F2;
  --tone1-bg:rgba(63,199,155,.15);  --tone1-fg:#57D6B4;
  --tone2-bg:rgba(228,176,92,.15);  --tone2-fg:#EFC078;
  --tone3-bg:rgba(229,120,130,.15); --tone3-fg:#F1919A;
  --tone4-bg:rgba(91,180,235,.15);  --tone4-fg:#7FC5F2;
  --tone5-bg:rgba(178,134,240,.15); --tone5-fg:#CFA3F5;
  --tone6-bg:rgba(154,199,100,.15); --tone6-fg:#B8DA85;
  --tone7-bg:rgba(139,145,158,.16); --tone7-fg:#ADB4C2;
}
"""

LIGHT_VARS = """
.stApp {
  --bg:#F4F5F7; --surface:#FFFFFF; --surface2:#EDEEF1;
  --border:#E4E5E9; --border-strong:#D2D4DA;
  --text:#1A1C21; --text-dim:#45484F; --muted:#63666E;
  --accent:#5A61D8; --accent-hover:#6C73E3; --accent-press:#4C53C7;
  --accent-soft:rgba(90,97,216,.10);
  --success:#178A62; --warning:#A97413; --danger:#CC4B5E;
  --success-bg:rgba(23,138,98,.10); --warning-bg:rgba(169,116,19,.10);
  --danger-bg:rgba(204,75,94,.10);
  --shadow-rest:0 1px 2px rgba(26,28,33,.06);
  --shadow-hover:0 8px 28px rgba(26,28,33,.10);
  --shadow:var(--shadow-hover);
  --focus-ring:0 0 0 2px color-mix(in srgb, var(--accent) 55%, transparent),
               0 0 0 5px color-mix(in srgb, var(--accent) 18%, transparent);
  --glass:rgba(244,245,247,.82);
  --tone0-bg:rgba(90,97,216,.10);  --tone0-fg:#4353D6;
  --tone1-bg:rgba(23,138,98,.10);  --tone1-fg:#0C7D57;
  --tone2-bg:rgba(169,116,19,.10); --tone2-fg:#96620D;
  --tone3-bg:rgba(204,75,94,.10);  --tone3-fg:#B3324A;
  --tone4-bg:rgba(2,110,166,.10);  --tone4-fg:#046EA6;
  --tone5-bg:rgba(105,56,239,.10); --tone5-fg:#5B2BC4;
  --tone6-bg:rgba(63,122,11,.10);  --tone6-fg:#3F7A0B;
  --tone7-bg:rgba(71,84,103,.10);  --tone7-fg:#475467;
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
.block-container { max-width: 1160px; padding: 1.5rem 1.3rem 4rem; }

h1 {
  font-size: clamp(1.6rem, 1.3rem + 1vw, 2rem) !important;
  font-weight: 800 !important;
  letter-spacing: -0.03em;
  line-height: 1.12;
}
h2 {
  font-size: clamp(1.08rem, 1rem + 0.35vw, 1.24rem) !important;
  font-weight: 700 !important;
  letter-spacing: -0.015em;
  line-height: 1.15;
}
h3 { font-size: 1rem !important; font-weight: 650 !important; line-height: 1.15; }
h1, h2, h3 { color: var(--text); }

[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
  color: var(--text-dim);
  line-height: 1.6;
}
[data-testid="stMarkdownContainer"] b, [data-testid="stMarkdownContainer"] strong {
  color: var(--text);
}
a { color: var(--accent); }

[data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] p {
  color: var(--muted) !important;
}
[data-testid="stWidgetLabel"] p { font-size: .86rem; }

/* Числа — табличные цифры везде, где есть счётчики. */
.bento-num, .hero-num, .qty-display, .box-count-num, .chip-count,
.badge, .badge-plain, td, [data-testid="stMetricValue"] {
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

/* ── Боковая панель: стекло + pill-навигация ────────────────────────── */
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
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 650;
}
.side-section {
  font-size: .68rem; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted); margin: .3rem 0 .45rem;
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
  box-shadow: 0 4px 16px color-mix(in srgb, var(--accent) 35%, transparent);
}
[data-testid="stBaseButton-primary"]:active,
[data-testid="stFormSubmitButton"] button[kind="primary"]:active {
  background: var(--accent-press);
  transform: translateY(1px);
}
/* Secondary — ghost на surface2: рамка появляется только на hover. */
[data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
  background: var(--surface2);
  border: 1px solid transparent;
  color: var(--text-dim);
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
  background: var(--surface2);
  border-color: var(--border-strong);
  color: var(--text);
}
[data-testid="stBaseButton-tertiary"], [data-testid="stBaseButton-borderless"] {
  background: transparent;
  color: var(--muted);
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

/* ── Экспандеры, поповеры, формы, segmented control ─────────────────── */
[data-testid="stExpander"] {
  background: var(--surface);
  border: 1px solid var(--hairline) !important;
  border-radius: 16px !important;
  overflow: hidden;
  box-shadow: var(--shadow-rest);
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
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 4px;
  transition: border-color .16s ease;
}
[data-testid="stSegmentedControl"] button {
  border-radius: 9px;
  padding: .42rem 1.05rem;
  font-size: .92rem;
  font-weight: 600;
  color: var(--text-dim);
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
  background: var(--accent);
  color: #fff;
}

/* ── Карточки-контейнеры (st.container(border=True, key="...")) ─────── */
[class*="st-key-"][class*="itemcard"], [class*="st-key-"][class*="boxcard"],
[class*="st-key-"][class*="loccard"], [class*="st-key-"][class*="info_card"],
[class*="st-key-"][class*="qr_card"], [class*="st-key-"][class*="qty_card"],
[class*="st-key-"][class*="form_card"], [class*="st-key-"][class*="empty_state"],
[class*="st-key-"][class*="trashrow"], [class*="st-key-"][class*="panel"] {
  background: var(--surface);
  border: 1px solid var(--hairline) !important;
  border-radius: 16px !important;
  padding: 1rem 1.1rem;
  box-shadow: var(--shadow-rest);
  transition: border-color .16s ease, box-shadow .16s ease;
}
[class*="st-key-"][class*="itemcard"]:hover, [class*="st-key-"][class*="boxcard"]:hover,
[class*="st-key-"][class*="loccard"]:hover, [class*="st-key-"][class*="trashrow"]:hover {
  border-color: var(--border-strong) !important;
  box-shadow: var(--shadow-hover);
}

/* Степпер количества: компактные кнопки 38px, крупная цифра.
   Без анимаций — карточки перерисовываются в фрагменте на каждый клик. */
[class*="st-key-"][class*="itemcard"] [data-testid^="stBaseButton-"] {
  min-width: 38px;
  min-height: 36px;
}
[class*="st-key-"][class*="itemcard"] [data-testid="stPopover"] > button {
  min-width: 38px;
}

/* ── Полоса отмены удаления: компактный danger-чип ───────────────────── */
.st-key-undo_strip {
  background: var(--danger-bg) !important;
  border: 1px solid color-mix(in srgb, var(--danger) 34%, transparent) !important;
  border-radius: 12px !important;
  padding: .45rem .8rem !important;
  box-shadow: none !important;
  animation: slide-down .24s ease-out both;
}
.st-key-undo_strip .item-meta { color: var(--text-dim); font-size: .82rem; }

/* ── Таблицы, алерты, код ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--hairline);
  border-radius: 14px;
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

/* ── Бренд в сайдбаре: компактный ───────────────────────────────────── */
.brand { display: flex; gap: 10px; align-items: center; padding: .25rem .1rem .55rem; }
.brand-logo {
  width: 34px; height: 34px; border-radius: 10px; flex: none;
  background: linear-gradient(135deg, var(--accent), #9F6CFF);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 40%, transparent);
}
.brand-name { font-weight: 800; font-size: .95rem; color: var(--text); line-height: 1.15; }
.brand-sub { font-size: .7rem; color: var(--muted); }

/* ── Hero-шапка страницы ────────────────────────────────────────────── */
.hero { margin: .1rem 0 1rem; }
.hero h1 { margin: 0; }
.hero-caption {
  color: var(--muted); font-size: .88rem; line-height: 1.5;
  margin-top: .35rem;
}

/* ── Bento-статистика (hero-плитка + компактные) ────────────────────── */
.bento {
  display: grid;
  gap: 12px;
  margin: .2rem 0 .6rem;
  grid-template-columns: minmax(220px, 1.25fr) 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  grid-template-areas:
    "hero a b"
    "hero c c";
}
.bento-tile {
  display: flex; gap: 12px; align-items: center;
  background: var(--surface);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 14px 17px;
  box-shadow: var(--shadow-rest);
  animation: rise-in .24s ease-out both;
  transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}
.bento-tile:nth-child(2) { grid-area: a; animation-delay: .04s; }
.bento-tile:nth-child(3) { grid-area: b; animation-delay: .08s; }
.bento-tile:nth-child(4) { grid-area: c; animation-delay: .12s; }
.bento-tile:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-hover);
}
.bento-hero { grid-area: hero; padding: 18px 22px; }
.hero-num {
  font-size: 2.6rem; font-weight: 800; line-height: 1.05;
  color: var(--text); letter-spacing: -0.02em;
}
.hero-label {
  font-size: .72rem; color: var(--muted); margin-top: 5px;
  text-transform: uppercase; letter-spacing: .07em;
}
.bento-num { font-size: 1.4rem; font-weight: 750; line-height: 1.1; color: var(--text); }
.bento-label {
  font-size: .68rem; color: var(--muted); margin-top: 3px;
  text-transform: uppercase; letter-spacing: .05em;
}
.icon-chip {
  width: 40px; height: 40px; border-radius: 999px; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 19px;
  background: var(--accent-soft);
}
.bento-hero .icon-chip { width: 48px; height: 48px; font-size: 23px; }

/* ── Секционные заголовки с caps-оверлайном ─────────────────────────── */
.section-block { margin: 1.35rem 0 .5rem; }
.section-overlay {
  font-size: .68rem; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted); margin-bottom: .18rem;
}
.section-title {
  font-size: 1.05rem; font-weight: 700; color: var(--text);
  letter-spacing: -0.01em; line-height: 1.2;
}

/* ── Чипы ───────────────────────────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center;
  padding: 1px 9px; border-radius: 999px;
  font-size: .72rem; font-weight: 650; line-height: 1.7;
  vertical-align: middle;
}
.badge.tone-0 { background: var(--tone0-bg); color: var(--tone0-fg); }
.badge.tone-1 { background: var(--tone1-bg); color: var(--tone1-fg); }
.badge.tone-2 { background: var(--tone2-bg); color: var(--tone2-fg); }
.badge.tone-3 { background: var(--tone3-bg); color: var(--tone3-fg); }
.badge.tone-4 { background: var(--tone4-bg); color: var(--tone4-fg); }
.badge.tone-5 { background: var(--tone5-bg); color: var(--tone5-fg); }
.badge.tone-6 { background: var(--tone6-bg); color: var(--tone6-fg); }
.badge.tone-7 { background: var(--tone7-bg); color: var(--tone7-fg); }
.badge-plain {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 1px 9px; border-radius: 999px;
  font-size: .72rem; font-weight: 600; line-height: 1.7;
  background: var(--surface2); color: var(--text-dim);
  vertical-align: middle;
}

/* ── Карточка вещи: имя, чипы, заметки ──────────────────────────────── */
.item-name { font-weight: 650; font-size: .98rem; color: var(--text); line-height: 1.35; }
.item-chips {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  margin-top: 6px;
}
.item-meta { color: var(--muted); font-size: .8rem; margin-top: 4px; line-height: 1.5; }
.item-notes {
  color: var(--text-dim); font-size: .82rem; margin-top: 6px; line-height: 1.5;
}
.qty-display {
  font-weight: 750; font-size: 1.15rem; text-align: center;
  color: var(--text); min-width: 2em;
}
.box-count { display: flex; align-items: baseline; gap: 6px; }
.box-count-num { font-size: 1.55rem; font-weight: 800; color: var(--text); }
.box-count-label { font-size: .74rem; color: var(--muted); }

/* ── Пустые состояния (в карточке) ──────────────────────────────────── */
.empty-state { text-align: center; padding: 1.7rem .6rem .9rem; }
.empty-icon {
  font-size: 2.4rem; margin-bottom: .35rem;
  width: 72px; height: 72px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface2); border: 1px solid var(--hairline);
  margin-left: auto; margin-right: auto;
  animation: breathe 3.2s ease-in-out infinite;
}
.empty-title {
  font-size: 1.02rem; font-weight: 700; color: var(--text); margin-top: .55rem;
}
.empty-hint { font-size: .86rem; color: var(--muted); margin-top: .2rem; }

/* ── Компактные hint-чипы и счётчики ────────────────────────────────── */
.chip-hint {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--surface2); border: 1px solid var(--hairline);
  border-radius: 999px; padding: 4px 12px;
  font-size: .78rem; color: var(--muted); line-height: 1.5;
  margin: .1rem 0 .7rem;
}
.chip-count {
  display: inline-flex; align-items: center;
  background: var(--accent-soft); color: var(--text);
  border-radius: 999px; padding: 4px 12px;
  font-size: .8rem; font-weight: 650; white-space: nowrap;
}

::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }

/* ── Адаптивность ───────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .block-container { padding: 1rem .85rem 3rem; }
  h1 { font-size: clamp(1.4rem, 1.2rem + 0.9vw, 1.6rem) !important; }
  .bento {
    grid-template-columns: 1fr 1fr;
    grid-template-areas:
      "hero hero"
      "a b"
      "c c";
    gap: 10px;
  }
  .bento-hero { padding: 15px 17px; }
  .hero-num { font-size: 2.1rem; }
  .bento-tile { padding: 12px 14px; animation: none; }
  .bento-num { font-size: 1.2rem; }
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
    """Переключатель светлой/тёмной темы (ghost-кнопка). Выбор сохраняется
    в URL (?theme=), поэтому переживает перезагрузку страницы; кроме того,
    приложение следует теме из меню Settings Streamlit, если явный параметр
    не задан."""
    label = "☀️ Светлая тема" if theme == "dark" else "🌙 Тёмная тема"
    if st.button(label, use_container_width=True, key="theme_toggle_btn"):
        st.query_params["theme"] = "light" if theme == "dark" else "dark"
        st.rerun()
