from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import pydeck as pdk
import streamlit as st

from data_utils import (
    ALLOWED_QUESTION_TYPES,
    CANONICAL_COLUMNS,
    add_unit_display,
    ensure_columns,
    explode_units,
    filter_dataframe,
    get_all_units,
    question_catalog,
    read_csv_bytes,
    read_csv_path,
    read_csv_url,
    to_download_csv,
    validate_dataframe,
)
from geo_utils import aggregate_points, add_point_visuals, build_areals, label_color_hex, map_view_state


APP_DIR = Path(__file__).parent
SAMPLE_DATA_PATH = APP_DIR / "data" / "sample_dialects.csv"
TEMPLATE_DATA_PATH = APP_DIR / "data" / "data_template.csv"

MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

GIS_SYSTEMS = [
    {
        "ГИС": "QGIS",
        "Назначение": "Открытая настольная ГИС для подготовки слоёв, проверки координат, экспорта GeoJSON/CSV.",
        "Что удобно для атласа": "Оцифровка районов, ручные изоглоссы, проверка CRS EPSG:4326.",
        "Форматы": "GeoPackage, GeoJSON, Shapefile, CSV, WMS/WMTS.",
        "Интерфейс": "Настольный, плагины, русская локализация.",
    },
    {
        "ГИС": "Esri ArcGIS",
        "Назначение": "Профессиональная экосистема для сложной геоаналитики и публикации веб-карт.",
        "Что удобно для атласа": "Геобазы, StoryMaps, сервисы ArcGIS Online/Enterprise.",
        "Форматы": "FileGDB, Feature Service, Shapefile, GeoJSON, CSV.",
        "Интерфейс": "ArcGIS Pro + веб-портал.",
    },
    {
        "ГИС": "MapInfo",
        "Назначение": "Настольная ГИС для тематического картографирования и региональной статистики.",
        "Что удобно для атласа": "Тематические карты по районам, импорт таблиц.",
        "Форматы": "TAB, MIF/MID, Shapefile, CSV.",
        "Интерфейс": "Настольный.",
    },
    {
        "ГИС": "Maptitude",
        "Назначение": "Картография, маршрутизация, территориальная аналитика.",
        "Что удобно для атласа": "Быстрые тематические карты и отчёты.",
        "Форматы": "Собственные слои, Shapefile, CSV.",
        "Интерфейс": "Настольный.",
    },
    {
        "ГИС": "ГИС Аксиома",
        "Назначение": "Российская ГИС-платформа для корпоративных и ведомственных задач.",
        "Что удобно для атласа": "Хранение пространственных слоёв и ведомственные справочники.",
        "Форматы": "Зависит от поставки: векторные слои, таблицы, обменные форматы.",
        "Интерфейс": "Настольный/корпоративный.",
    },
    {
        "ГИС": "ГИС Панорама",
        "Назначение": "Российская профессиональная ГИС для топокарт и кадастровых/ведомственных данных.",
        "Что удобно для атласа": "Работа с топографической основой, экспорт слоёв.",
        "Форматы": "SXF/TX, MIF/MID, Shapefile, GeoTIFF, CSV и др.",
        "Интерфейс": "Настольный и серверные компоненты.",
    },
    {
        "ГИС": "NextGIS",
        "Назначение": "Веб-ГИС и инструменты публикации карт.",
        "Что удобно для атласа": "Публикация районов/ареалов как веб-слоёв, совместная работа.",
        "Форматы": "GeoJSON, GeoPackage, Shapefile, WMS/WFS, CSV.",
        "Интерфейс": "Веб + мобильные/настольные инструменты.",
    },
    {
        "ГИС": "ГИС ИНТЕГРО",
        "Назначение": "ГИС для интеграции пространственных и тематических данных.",
        "Что удобно для атласа": "Комплексное хранение, аналитика, ведомственные данные.",
        "Форматы": "Зависит от конфигурации и модулей.",
        "Интерфейс": "Настольный/корпоративный.",
    },
]


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


@st.cache_data(ttl=90, show_spinner=False)
def cached_url_csv(url: str) -> pd.DataFrame:
    return read_csv_url(url)


@st.cache_data(ttl=300, show_spinner=False)
def cached_geojson_url(url: str) -> dict:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def page_setup() -> None:
    st.set_page_config(
        page_title="Интерактивный атлас русских говоров Удмуртии",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
        :root {
            --app-bg: #f8fafc;
            --panel-bg: #ffffff;
            --panel-soft: #f1f5f9;
            --text-main: #0f172a;
            --text-muted: #475569;
            --border-soft: #dbe3ef;
            --accent-soft: #e0f2fe;
            --accent: #2563eb;
        }

        .stApp {
            background: linear-gradient(180deg, var(--app-bg) 0%, #ffffff 100%);
            color: var(--text-main);
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stHeader"]::before {
            background: transparent;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
            border-right: 1px solid var(--border-soft);
        }

        section[data-testid="stSidebar"] > div {
            background: transparent !important;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {
            color: var(--text-main) !important;
        }

        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: var(--text-main) !important;
            border-color: #cbd5e1 !important;
        }

        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {
            background: #ffffff !important;
            color: var(--text-main) !important;
        }

        [data-baseweb="option"],
        [data-baseweb="option"] span,
        [data-baseweb="menu"] span {
            color: var(--text-main) !important;
        }

        [data-baseweb="tag"] {
            background: var(--accent-soft) !important;
            color: #075985 !important;
        }

        [data-baseweb="tag"] span {
            color: #075985 !important;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            padding: 12px 16px;
            box-shadow: 0 1px 10px rgba(15, 23, 42, .06);
            color: var(--text-main);
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] div,
        div[data-testid="stMetric"] span {
            color: var(--text-main) !important;
        }

        .hero {
            position: relative;
            isolation: isolate;
            overflow: hidden;
            padding: 22px 24px;
            border-radius: 22px;
            background: #ffffff;
            border: 1px solid var(--border-soft);
            box-shadow: 0 1px 14px rgba(15, 23, 42, .06);
            margin-bottom: 18px;
            color: var(--text-main);
        }

        .hero::before {
            content: "";
            position: absolute;
            inset: 0;
            z-index: -1;
            pointer-events: none;
            background:
              radial-gradient(circle at 12% 20%, rgba(37, 99, 235, .10), transparent 30%),
              radial-gradient(circle at 88% 0%, rgba(14, 165, 233, .10), transparent 28%);
        }

        .hero h1 {
            margin: 0;
            font-size: 2.1rem;
            line-height: 1.18;
            color: var(--text-main) !important;
        }

        .hero p {
            margin: 8px 0 0 0;
            color: var(--text-muted) !important;
            line-height: 1.5;
        }

        .card {
            background: #ffffff;
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 1px 12px rgba(15, 23, 42, .06);
            margin-bottom: 12px;
            color: var(--text-main);
        }

        .card,
        .card * {
            color: var(--text-main) !important;
        }

        .small {
            color: var(--text-muted) !important;
            font-size: .91rem;
        }

        .legend-item {
            display: flex;
            gap: 8px;
            align-items: center;
            margin: 5px 0;
            font-size: .9rem;
        }

        .swatch {
            width: 14px;
            height: 14px;
            border-radius: 4px;
            border: 1px solid rgba(15, 23, 42, .25);
            display: inline-block;
            flex: 0 0 auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(df: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>🧭 Интерактивная карта русских говоров Удмуртии</h1>
          <p>Атласная панель: населённые пункты, районы, ландшафт, диалектные единицы, ареалы, изоглоссы и комментарии.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Записей", f"{len(df):,}".replace(",", " "))
    c2.metric("Пунктов", df["settlement"].nunique())
    c3.metric("Районов", df["district"].nunique())
    c4.metric("Вопросов", df["question"].nunique())
    c5.metric("Единиц", len(get_all_units(df)))


def load_data_sidebar() -> tuple[pd.DataFrame, str, str]:
    st.sidebar.markdown("## Источник данных")

    secret_url = get_secret("DATA_CSV_URL")
    secret_edit_url = get_secret("REMOTE_TABLE_EDIT_URL")

    source_kind = st.sidebar.radio(
        "Как загрузить таблицу",
        ["Демо-данные", "Google Sheets / CSV URL", "Загрузить CSV"],
        index=0 if not secret_url else 1,
    )

    source_note = ""
    editor_url = secret_edit_url

    if st.sidebar.button("Обновить кэш данных"):
        st.cache_data.clear()
        st.sidebar.success("Кэш очищен. Данные будут перечитаны.")

    if source_kind == "Google Sheets / CSV URL":
        url = st.sidebar.text_input(
            "CSV URL",
            value=secret_url,
            help="Подходит опубликованный CSV Google Sheets или любой HTTPS CSV.",
        )
        editor_url = st.sidebar.text_input(
            "Ссылка на редактирование таблицы",
            value=secret_edit_url,
            help="Необязательно: ссылка на Google Sheets для редакторов.",
        )
        if not url:
            st.sidebar.warning("Вставьте URL CSV или задайте DATA_CSV_URL в secrets.")
            return read_csv_path(str(SAMPLE_DATA_PATH)), "Демо-данные: URL не задан", editor_url
        try:
            return cached_url_csv(url), "Удалённая таблица CSV/Google Sheets", editor_url
        except Exception as exc:
            st.sidebar.error(f"Не удалось загрузить URL: {exc}")
            return read_csv_path(str(SAMPLE_DATA_PATH)), "Демо-данные: ошибка URL", editor_url

    if source_kind == "Загрузить CSV":
        uploaded = st.sidebar.file_uploader("CSV-файл", type=["csv"])
        if uploaded is not None:
            try:
                return read_csv_bytes(uploaded.getvalue()), f"Загружен файл: {uploaded.name}", editor_url
            except Exception as exc:
                st.sidebar.error(str(exc))
        source_note = "Демо-данные: CSV не загружен"

    return read_csv_path(str(SAMPLE_DATA_PATH)), source_note or "Демо-данные из пакета", editor_url


def sidebar_filters(df: pd.DataFrame) -> dict:
    st.sidebar.markdown("## Фильтры атласа")
    regions = sorted([x for x in df["region"].dropna().unique() if x])
    selected_regions = st.sidebar.multiselect("Регионы", regions, default=regions)

    district_pool = df[df["region"].isin(selected_regions)] if selected_regions else df
    districts = sorted([x for x in district_pool["district"].dropna().unique() if x])
    selected_districts = st.sidebar.multiselect("Районы / округа", districts, default=[])

    catalog = question_catalog(df)
    question_labels = ["Все вопросы"] + [
        f"{row.question_id} · {row.question}" for row in catalog.itertuples()
    ]
    selected_label = st.sidebar.selectbox("Карта / вопрос", question_labels, index=0)
    selected_question = "Все вопросы"
    if selected_label != "Все вопросы":
        selected_question = selected_label.split(" · ", 1)[1]

    unit_query = st.sidebar.text_input("Поиск лингвистической единицы", placeholder="например: [ɣ], ляда, -ут")
    text_query = st.sidebar.text_input("Общий поиск", placeholder="пункт, район, комментарий")

    color_mode = st.sidebar.radio(
        "Раскраска точек",
        ["Диалектные единицы", "Ландшафт", "Тип вопроса", "Атлас"],
        index=0,
    )
    show_areals = st.sidebar.checkbox("Показывать ареалы", value=True)
    show_isoglosses = st.sidebar.checkbox("Показывать изоглоссы", value=True)
    show_labels = st.sidebar.checkbox("Подписи пунктов", value=False)

    st.sidebar.markdown("## Доп. геослой")
    geojson_url = st.sidebar.text_input(
        "GeoJSON границ/районов",
        value=get_secret("BOUNDARY_GEOJSON_URL"),
        help="Необязательно. Слой должен быть в WGS84 (EPSG:4326).",
    )

    return {
        "regions": selected_regions,
        "districts": selected_districts,
        "selected_question": selected_question,
        "unit_query": unit_query,
        "text_query": text_query,
        "color_mode": color_mode,
        "show_areals": show_areals,
        "show_isoglosses": show_isoglosses,
        "show_labels": show_labels,
        "geojson_url": geojson_url,
    }


def make_deck(
    df: pd.DataFrame,
    selected_question: str = "Все вопросы",
    color_mode: str = "Диалектные единицы",
    show_areals: bool = True,
    show_isoglosses: bool = True,
    show_labels: bool = False,
    geojson_url: str = "",
    height: int = 640,
) -> tuple[pdk.Deck | None, pd.DataFrame, list[dict]]:
    df = add_unit_display(ensure_columns(df))
    points_df = aggregate_points(df)
    if points_df.empty:
        return None, points_df, []

    points_df = add_point_visuals(points_df, color_mode)

    layers = []

    if geojson_url.strip():
        try:
            geojson = cached_geojson_url(geojson_url.strip())
            layers.append(
                pdk.Layer(
                    "GeoJsonLayer",
                    data=geojson,
                    stroked=True,
                    filled=False,
                    get_line_color=[30, 41, 59, 130],
                    get_line_width=260,
                    line_width_min_pixels=1,
                    pickable=True,
                )
            )
        except Exception as exc:
            st.warning(f"GeoJSON-слой не загружен: {exc}")

    areals: list[dict] = []
    if selected_question != "Все вопросы":
        exploded = explode_units(df)
        areals = build_areals(exploded, "linguistic_unit")

        if show_areals and areals:
            layers.append(
                pdk.Layer(
                    "PolygonLayer",
                    data=areals,
                    get_polygon="polygon",
                    get_fill_color="fill_color",
                    get_line_color="line_color",
                    line_width_min_pixels=1,
                    stroked=True,
                    filled=True,
                    pickable=True,
                    auto_highlight=True,
                )
            )

        if show_isoglosses and areals:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    data=areals,
                    get_path="path",
                    get_color="line_color",
                    width_scale=1,
                    width_min_pixels=3,
                    pickable=True,
                )
            )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=points_df,
            get_position="[longitude, latitude]",
            get_fill_color="color",
            get_line_color="outline_color",
            get_radius="radius_m",
            line_width_min_pixels=1,
            stroked=True,
            filled=True,
            radius_min_pixels=5,
            radius_max_pixels=28,
            pickable=True,
            auto_highlight=True,
        )
    )

    if show_labels:
        layers.append(
            pdk.Layer(
                "TextLayer",
                data=points_df,
                get_position="[longitude, latitude]",
                get_text="short_label",
                get_size=13,
                get_color=[15, 23, 42, 230],
                get_alignment_baseline="'bottom'",
                get_pixel_offset=[0, -12],
                pickable=False,
            )
        )

    view = pdk.ViewState(**map_view_state(points_df))
    deck = pdk.Deck(
        map_style=MAP_STYLE,
        initial_view_state=view,
        layers=layers,
        tooltip={
            "html": "{tooltip}<br/><b>Цвет:</b> {color_label}",
            "style": {"backgroundColor": "#ffffff", "color": "#0f172a", "fontSize": "12px", "border": "1px solid #cbd5e1", "boxShadow": "0 4px 18px rgba(15, 23, 42, .14)"},
        },
        height=height,
    )
    return deck, points_df, areals


def render_legend(points_df: pd.DataFrame, areals: list[dict]) -> None:
    if points_df.empty:
        return

    labels = (
        points_df.groupby("color_label")
        .agg(points=("settlement", "nunique"), color=("color_label", "first"))
        .reset_index()
        .sort_values(["points", "color_label"], ascending=[False, True])
    )

    st.markdown("#### Легенда")
    html = ['<div class="card">']
    for _, row in labels.head(16).iterrows():
        html.append(
            f'<div class="legend-item"><span class="swatch" style="background:{label_color_hex(row["color"])}"></span>'
            f'<span>{row["color_label"]} · {int(row["points"])}</span></div>'
        )
    if len(labels) > 16:
        html.append(f'<div class="small">Показано 16 из {len(labels)} значений.</div>')
    html.append("</div>")
    st.markdown("\n".join(html), unsafe_allow_html=True)

    if areals:
        st.markdown("#### Авто-ареалы")
        area_df = pd.DataFrame(areals)[["label", "count"]].rename(
            columns={"label": "единица", "count": "пунктов в ареале"}
        )
        st.dataframe(area_df, hide_index=True, use_container_width=True)


def render_atlas_page(df: pd.DataFrame, filters: dict) -> None:
    st.subheader("Карта: пункты, ареалы, изоглоссы")

    filtered = filter_dataframe(
        df,
        regions=filters["regions"],
        districts=filters["districts"],
        question=filters["selected_question"],
        unit_query=filters["unit_query"],
        text_query=filters["text_query"],
    )

    left, right = st.columns([3.2, 1.15], gap="large")
    with left:
        deck, points_df, areals = make_deck(
            filtered,
            selected_question=filters["selected_question"],
            color_mode=filters["color_mode"],
            show_areals=filters["show_areals"],
            show_isoglosses=filters["show_isoglosses"],
            show_labels=filters["show_labels"],
            geojson_url=filters["geojson_url"],
        )
        if deck is None:
            st.warning("Нет точек с координатами для выбранных фильтров.")
        else:
            st.pydeck_chart(deck, use_container_width=True)
    with right:
        render_legend(points_df if "points_df" in locals() else pd.DataFrame(), areals if "areals" in locals() else [])
        st.markdown(
            """
            <div class="card small">
            <b>Важно:</b> автоматические ареалы построены по выпуклой оболочке точек и подходят для демонстрации.
            Для научной публикации лучше загрузить вручную проверенный GeoJSON-слой из QGIS/ArcGIS/NextGIS.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Таблица выбранных записей", expanded=False):
        show_cols = [
            "region",
            "district",
            "settlement",
            "landscape",
            "atlas_system",
            "question_type",
            "question_id",
            "question",
            "unit_display",
            "comment",
        ]
        st.dataframe(filtered[show_cols], hide_index=True, use_container_width=True)
        st.download_button(
            "Скачать выбранные записи CSV",
            data=to_download_csv(filtered),
            file_name="dialekt_selected_records.csv",
            mime="text/csv",
        )


def render_maps_page(df: pd.DataFrame) -> None:
    st.subheader("Поиск и демонстрация карт")
    catalog = question_catalog(df)

    q = st.text_input("Поиск карты по коду, вопросу, разделу или атласу", placeholder="ДАРЯ фонетика / D-FON / дождь")
    if q:
        needle = q.lower()
        visible = catalog[
            catalog.apply(lambda row: needle in " ".join(map(str, row.values)).lower(), axis=1)
        ].copy()
    else:
        visible = catalog.copy()

    st.dataframe(
        visible.rename(
            columns={
                "question_id": "код",
                "question": "вопрос",
                "atlas_system": "атлас",
                "question_type": "тип",
                "settlements": "пунктов",
                "regions": "регионов",
                "districts": "районов",
                "units": "единицы",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    if visible.empty:
        st.info("Поиск не дал результатов.")
        return

    selected = st.selectbox(
        "Открыть карту",
        [f"{row.question_id} · {row.question}" for row in visible.itertuples()],
    )
    question = selected.split(" · ", 1)[1]
    subset = filter_dataframe(df, question=question)

    st.markdown("### Демонстрация выбранной карты")
    left, right = st.columns([3, 1.2], gap="large")
    with left:
        deck, points_df, areals = make_deck(
            subset,
            selected_question=question,
            color_mode="Диалектные единицы",
            show_areals=True,
            show_isoglosses=True,
            show_labels=True,
            height=520,
        )
        if deck:
            st.pydeck_chart(deck, use_container_width=True)
    with right:
        passport = question_catalog(subset).iloc[0]
        st.markdown(
            f"""
            <div class="card">
            <b>Паспорт карты</b><br/>
            Код: {passport['question_id']}<br/>
            Атлас: {passport['atlas_system']}<br/>
            Тип: {passport['question_type']}<br/>
            Пунктов: {int(passport['settlements'])}<br/>
            Единицы: {passport['units']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_legend(points_df if "points_df" in locals() else pd.DataFrame(), areals if "areals" in locals() else [])

    st.download_button(
        "Скачать данные этой карты",
        data=to_download_csv(subset),
        file_name=f"{selected.split(' · ', 1)[0]}_map_data.csv",
        mime="text/csv",
    )


def render_points_page(df: pd.DataFrame) -> None:
    st.subheader("Пункты, районы и регионы")

    c1, c2, c3 = st.columns(3)
    with c1:
        region = st.selectbox("Регион", ["Все регионы"] + sorted(df["region"].unique()))
    region_df = df if region == "Все регионы" else df[df["region"] == region]
    with c2:
        district = st.selectbox("Район", ["Все районы"] + sorted(region_df["district"].unique()))
    district_df = region_df if district == "Все районы" else region_df[region_df["district"] == district]
    with c3:
        settlement_query = st.text_input("Поиск населённого пункта", placeholder="Ижевск, Сарапул...")

    if settlement_query:
        district_df = district_df[
            district_df["settlement"].str.lower().str.contains(settlement_query.lower(), na=False)
        ]

    settlements = sorted(district_df["settlement"].unique())
    if not settlements:
        st.info("По выбранным условиям пунктов нет.")
        return

    selected_settlement = st.selectbox("Открыть пункт", settlements)
    point_df = add_unit_display(district_df[district_df["settlement"] == selected_settlement])

    left, right = st.columns([1.15, 2.3], gap="large")
    with left:
        st.markdown(
            f"""
            <div class="card">
            <b>{selected_settlement}</b><br/>
            Регион: {point_df['region'].iloc[0]}<br/>
            Район: {point_df['district'].iloc[0]}<br/>
            Ландшафт: {point_df['landscape'].iloc[0]}<br/>
            Вопросов: {point_df['question'].nunique()}<br/>
            Координаты: {point_df['latitude'].iloc[0]}, {point_df['longitude'].iloc[0]}
            </div>
            """,
            unsafe_allow_html=True,
        )
        deck, _, _ = make_deck(point_df, color_mode="Тип вопроса", show_areals=False, show_isoglosses=False, height=360)
        if deck:
            st.pydeck_chart(deck, use_container_width=True)
    with right:
        st.markdown("#### Данные пункта")
        display = point_df[
            ["atlas_system", "question_type", "question_id", "question", "unit_display", "comment", "source"]
        ].rename(
            columns={
                "atlas_system": "атлас",
                "question_type": "тип",
                "question_id": "код",
                "question": "вопрос",
                "unit_display": "единицы",
                "comment": "комментарий",
                "source": "источник",
            }
        )
        st.dataframe(display, hide_index=True, use_container_width=True)

    st.markdown("### Сводка выбранной территории")
    summary = (
        add_unit_display(district_df)
        .groupby(["region", "district", "settlement"], dropna=False)
        .agg(questions=("question", "nunique"), units=("unit_display", lambda s: len(set("; ".join(s).split("; ")))))
        .reset_index()
        .rename(
            columns={
                "region": "регион",
                "district": "район",
                "settlement": "пункт",
                "questions": "вопросов",
                "units": "единиц",
            }
        )
    )
    st.dataframe(summary, hide_index=True, use_container_width=True)


def render_units_page(df: pd.DataFrame) -> None:
    st.subheader("Поиск лингвистических единиц")

    all_units = get_all_units(df)
    query = st.text_input("Введите единицу или часть формы", placeholder="[ɣ], ляда, проливень, -ут")
    visible_units = [u for u in all_units if query.lower() in u.lower()] if query else all_units

    if not visible_units:
        st.info("Единицы не найдены.")
        return

    selected_unit = st.selectbox("Единица", visible_units)
    df_units = explode_units(df)
    subset = df_units[df_units["linguistic_unit"].str.lower() == selected_unit.lower()]
    subset = add_unit_display(subset)

    c1, c2, c3 = st.columns(3)
    c1.metric("Записей", len(subset))
    c2.metric("Пунктов", subset["settlement"].nunique())
    c3.metric("Вопросов", subset["question"].nunique())

    left, right = st.columns([2.4, 1.3], gap="large")
    with left:
        deck, points_df, _ = make_deck(
            subset,
            selected_question="Все вопросы",
            color_mode="Тип вопроса",
            show_areals=False,
            show_isoglosses=False,
            show_labels=True,
            height=520,
        )
        if deck:
            st.pydeck_chart(deck, use_container_width=True)
    with right:
        st.markdown("#### Распределение по вопросам")
        by_question = (
            subset.groupby(["question_id", "question"])
            .agg(points=("settlement", "nunique"))
            .reset_index()
            .sort_values("points", ascending=False)
        )
        st.dataframe(by_question, hide_index=True, use_container_width=True)

        st.markdown("#### По регионам")
        by_region = subset.groupby("region").agg(points=("settlement", "nunique")).sort_values("points", ascending=False)
        st.bar_chart(by_region)

    st.markdown("#### Все вхождения")
    st.dataframe(
        subset[
            ["region", "district", "settlement", "landscape", "atlas_system", "question_type", "question", "comment"]
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_data_page(df: pd.DataFrame, source_note: str, editor_url: str) -> None:
    st.subheader("Таблица данных и удалённое редактирование")

    st.markdown(
        f"""
        <div class="card">
        <b>Текущий источник:</b> {source_note}<br/>
        Таблица редактируется удалённо в Google Sheets или другом CSV-источнике, а приложение перечитывает её по CSV URL.
        Для защищённого рабочего процесса храните ссылку CSV и ссылку редактора в Streamlit secrets.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if editor_url:
        st.link_button("Открыть таблицу для редактирования", editor_url)
    else:
        st.info("Добавьте REMOTE_TABLE_EDIT_URL в secrets или вставьте ссылку в боковой панели, чтобы показывать кнопку редактирования.")

    issues = validate_dataframe(df)
    st.markdown("### Проверка таблицы")
    if issues:
        st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)
    else:
        st.success("Ошибок в обязательных полях не найдено.")

    st.markdown("### Редактор текущей копии")
    st.caption("Изменения здесь не записываются в Google Sheets автоматически; используйте редактор как песочницу и скачайте CSV.")
    edited = st.data_editor(
        df[CANONICAL_COLUMNS + [c for c in df.columns if c not in CANONICAL_COLUMNS]],
        num_rows="dynamic",
        use_container_width=True,
        key="local_data_editor",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Скачать отредактированную копию CSV",
            data=to_download_csv(edited),
            file_name="dialekt_udmurtii_edited.csv",
            mime="text/csv",
        )
    with col_b:
        st.download_button(
            "Скачать шаблон таблицы",
            data=TEMPLATE_DATA_PATH.read_bytes(),
            file_name="dialekt_udmurtii_template.csv",
            mime="text/csv",
        )

    st.markdown("### Обязательная структура")
    schema = pd.DataFrame(
        [
            ["region", "область / край / республика", "да"],
            ["district", "район", "да"],
            ["settlement", "населённый пункт", "да"],
            ["latitude, longitude", "координаты WGS84", "для карты"],
            ["landscape", "ландшафт / тип местности", "желательно"],
            ["atlas_system", "ДАРЯ или ЛАРНГ", "желательно"],
            ["question_type", "раздел вопроса: ДАРЯ/ЛАРНГ", "да"],
            ["question_id", "код вопроса", "желательно"],
            ["question", "формулировка вопроса", "да"],
            ["linguistic_unit_1..n", "варианты / ответы", "да"],
            ["comment", "комментарий к пункту или карте", "желательно"],
        ],
        columns=["Поле", "Что хранит", "Статус"],
    )
    st.dataframe(schema, hide_index=True, use_container_width=True)


def render_gis_page() -> None:
    st.subheader("ГИС-справочник для проекта")

    st.markdown(
        """
        <div class="card">
        Этот раздел нужен, чтобы связать учебное приложение с географическими информационными системами:
        подготовка границ районов, импорт CSV, экспорт GeoJSON, ручная правка изоглосс, публикация веб-слоёв.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.dataframe(pd.DataFrame(GIS_SYSTEMS), hide_index=True, use_container_width=True)

    st.markdown("### Рекомендуемый рабочий процесс")
    st.markdown(
        """
        1. В QGIS/ArcGIS/NextGIS подготовьте слой районов, регионов или ландшафтных зон.
        2. Проверьте систему координат: для веб-карты нужен WGS84, EPSG:4326.
        3. Экспортируйте слой в GeoJSON и опубликуйте файл по HTTPS либо добавьте его в репозиторий.
        4. Вставьте ссылку в поле «GeoJSON границ/районов» в боковой панели.
        5. Табличные диалектные данные храните отдельно: Google Sheets/CSV остаётся главным источником.
        """
    )

    st.markdown("### Форматы обмена")
    formats = pd.DataFrame(
        [
            ["CSV", "таблица пунктов, вопросов и единиц", "обязательный простой формат"],
            ["GeoJSON", "границы районов, ареалы, ручные изоглоссы", "лучший формат для веб-карты"],
            ["GeoPackage", "рабочий проект в QGIS", "удобен для хранения нескольких слоёв"],
            ["Shapefile", "обмен со старыми ГИС", "можно конвертировать в GeoJSON"],
            ["WMS/WMTS", "подложки и топографические сервисы", "подключается через ГИС или отдельную веб-карту"],
        ],
        columns=["Формат", "Назначение", "Комментарий"],
    )
    st.dataframe(formats, hide_index=True, use_container_width=True)


def render_help_page() -> None:
    st.subheader("Инструкция пользователя")

    st.markdown(
        """
        ### Для зрителя
        Откройте вкладку **Атлас**, выберите регион, район, карту-вопрос или лингвистическую единицу.
        Точки показывают населённые пункты, цвет — выбранный режим легенды. При наведении видны вопрос,
        единицы, ландшафт и комментарий.

        ### Для редактора таблицы
        Заполняйте Google Sheets по шаблону: одна строка = один населённый пункт + один вопрос.
        Для нескольких ответов используйте столбцы `linguistic_unit_1`, `linguistic_unit_2`, `linguistic_unit_3`
        или разделяйте варианты точкой с запятой. После редактирования нажмите **Обновить кэш данных** в боковой панели.

        ### Для составителя карт
        Карта считается вопросом атласа. Чтобы добавить новую карту, внесите новый `question_id`, `question`,
        `atlas_system`, `question_type` и заполните ответы по пунктам. Во вкладке **Карты** появится паспорт карты,
        варианты единиц, автоматические ареалы и контурные изоглоссы.

        ### Типы вопросов
        Для ДАРЯ используйте разделы: `ДАРЯ: фонетика`, `ДАРЯ: морфология`, `ДАРЯ: синтаксис`, `ДАРЯ: лексика`.
        Для ЛАРНГ используйте тематические лексические разделы: природа, растительный мир, животный мир,
        человек, материальная культура, духовная культура, социальная сфера.

        ### Ограничения демонстрационной версии
        Авто-изоглоссы строятся по выпуклой оболочке точек. Это удобно для учебной демонстрации, но научные
        границы лучше рисовать и проверять в QGIS/ArcGIS/NextGIS, затем загружать как GeoJSON.
        """
    )

    st.markdown("### Допустимые значения `question_type`")
    st.dataframe(pd.DataFrame({"question_type": ALLOWED_QUESTION_TYPES}), hide_index=True, use_container_width=True)

    st.markdown("### Быстрый запуск")
    st.code(
        """pip install -r requirements.txt
streamlit run streamlit_app.py""",
        language="bash",
    )


def main() -> None:
    page_setup()
    df, source_note, editor_url = load_data_sidebar()
    df = ensure_columns(df)

    filters = sidebar_filters(df)
    render_header(df)

    st.caption(f"Источник: {source_note}")

    page = st.radio(
        "Раздел",
        ["Атлас", "Карты", "Пункты", "Единицы", "Таблица", "ГИС", "Инструкция"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if page == "Атлас":
        render_atlas_page(df, filters)
    elif page == "Карты":
        render_maps_page(df)
    elif page == "Пункты":
        render_points_page(df)
    elif page == "Единицы":
        render_units_page(df)
    elif page == "Таблица":
        render_data_page(df, source_note, editor_url)
    elif page == "ГИС":
        render_gis_page()
    else:
        render_help_page()


if __name__ == "__main__":
    main()
