"""Ящик: карточка выбранного ящика, QR-код и содержимое."""

from __future__ import annotations

import html as html_lib

import base64

import streamlit as st

from app.context import get_service
from app.ui.forms import box_create_form
from app.ui.helpers import (
    box_label_map,
    empty_state,
    load_all,
    location_label_map,
    page_header,
    place_badge,
    qty_total,
)
from app.ui.item_cards import render_box_contents
from app.ui.qr import qr_png
from app.ui.registry import PAGES
from app.ui.trash import NO_LOCATION_LABEL


def _qr_block(png: bytes, box_name: str, box_id: str) -> None:
    """Компактный QR в карточке ящика.

    Клик по коду открывает увеличенную копию поверх страницы, клик по фону
    или Esc закрывает. Чистый HTML+JS без перезагрузки страницы и без кнопок:
    Streamlit санитизирует разметку (инлайн-обработчики вырезаются), поэтому
    слушатели событий вешаются из <script> — st.html с
    ``unsafe_allow_javascript=True`` выполняет их в общем документе.
    """
    data_uri = f"data:image/png;base64,{base64.b64encode(png).decode()}"
    title = html_lib.escape(box_name.strip() or box_id)
    thumb_id = f"qr-thumb-{box_id}"
    overlay_id = f"qr-overlay-{box_id}"
    st.html(
        f"""
<img id="{thumb_id}" src="{data_uri}" width="104"
     style="cursor:zoom-in;border-radius:8px;background:#fff;padding:4px"
     alt="QR-код ящика">
<div id="{overlay_id}" style="display:none;position:fixed;inset:0;z-index:99990;
     background:rgba(0,0,0,0.66);backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);
     align-items:center;justify-content:center;cursor:zoom-out">
  <div style="background:#fff;padding:26px 26px 16px;border-radius:16px;text-align:center;
       box-shadow:0 18px 60px rgba(0,0,0,.4)">
    <img src="{data_uri}" style="width:min(60vh,420px);height:auto;border-radius:8px" alt="QR-код ящика">
    <div style="margin-top:10px;color:#333;font:14px/1.4 system-ui,sans-serif">📦 {title}<br>
      <span style="color:#888;font-size:12px">Наведите камеру телефона — откроется содержимое ящика.<br>Клик по фону или Esc — закрыть.</span>
    </div>
  </div>
</div>
<script>
(function() {{
  var thumb = document.getElementById("{thumb_id}");
  var overlay = document.getElementById("{overlay_id}");
  function close() {{ overlay.style.display = "none"; }}
  thumb.addEventListener("click", function() {{ overlay.style.display = "flex"; }});
  overlay.addEventListener("click", close);
  overlay.firstElementChild.addEventListener("click", function(e) {{ e.stopPropagation(); }});
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape") close();
  }});
}})();
</script>
""",
        unsafe_allow_javascript=True,
    )


def page_box_view() -> None:
    boxes, items, locations = load_all()
    page_header("📦 Содержимое ящика", page_key="box")

    with st.expander("➕ Новый ящик", expanded=boxes.empty):
        box_create_form("form_box_view_add", locations)

    if boxes.empty:
        empty_state(
            "📦", "Пока нет ни одного ящика",
            "Создайте ящик, чтобы раскладывать по нему вещи.",
            cta_label="Добавить первый ящик", cta_key="box_cta_add", cta_page=PAGES.get("add"),
        )
        return

    labels = box_label_map(boxes, locations)
    loc_names = location_label_map(locations)

    # Глубокая ссылка из QR-кода: /box?box=<id>.
    requested = st.query_params.get("box")
    if requested:
        if requested in labels:
            st.session_state["box_select"] = requested
        st.query_params.pop("box")

    box_id = st.selectbox(
        "Выберите ящик",
        options=list(labels.keys()),
        format_func=lambda x: labels.get(x, x),
        key="box_select",
    )
    box_matches = boxes[boxes["ID"] == box_id]
    if box_matches.empty:
        # Кэш мог протухнуть между чтением списка и рендером (параллельная
        # запись в другом потоке, выбор указывает на исчезнувший ящик) —
        # берём первый доступный вместо IndexError.
        box_matches = boxes
    box_row = box_matches.iloc[0]
    box_id = str(box_row["ID"])

    # Единая карточка ящика: слева — информация, справа — QR-код (не выходит
    # за границы карточки, по вертикали центрирован относительно текста).
    inside = items[items["Ящик_ID"].astype(str) == box_id]
    with st.container(border=True, key="box_info_card"):
        info_col, qr_col = st.columns([3, 1], vertical_alignment="center", gap="small")
        with info_col:
            st.markdown(
                f'<div class="item-name" style="font-size:1.15rem">📦 {html_lib.escape(str(box_row["Название"]))}</div>',
                unsafe_allow_html=True,
            )
            place = loc_names.get(str(box_row["Место_ID"]), "")
            chips = place_badge(place) or f'<span class="badge-plain">{NO_LOCATION_LABEL}</span>'
            st.markdown(f'<div class="item-chips">{chips}</div>', unsafe_allow_html=True)
            if box_row["Описание"]:
                st.markdown(
                    f'<div class="item-notes">ℹ️ {html_lib.escape(str(box_row["Описание"]))}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div class="item-meta">{len(inside)} поз. · {qty_total(inside)} ед.</div>',
                unsafe_allow_html=True,
            )
        with qr_col:
            _qr_block(qr_png(box_id), str(box_row["Название"]), box_id)

    render_box_contents(box_id, labels)
