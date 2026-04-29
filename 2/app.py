from __future__ import annotations

import colorsys
import hashlib
import html
import math
import re
from pathlib import Path
from typing import Iterable

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen, Geocoder
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from scipy.spatial import ConvexHull, QhullError
from streamlit_folium import st_folium

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SAMPLE_DATA_PATH = DATA_DIR / "sample_dialects.csv"
TEMPLATE_DATA_PATH = DATA_DIR / "data_template.csv"

ALL_COLUMNS = [
    "region",
    "district",
    "settlement",
    "settlement_type",
    "latitude",
    "longitude",
    "landscape",
    "atlas_system",
    "question_type",
    "question_id",
    "question",
    "linguistic_unit_1",
    "linguistic_unit_2",
    "linguistic_unit_3",
    "comment",
    "source",
    "year",
]

QUESTION_SELECTION = {
    "ДАРЯ": ["D-FON-01", "D-FON-02", "D-MOR-01"],
    "ЛАРНГ": ["L-NAT-01", "L-NAT-02", "L-MAT-01"],
}

QUESTION_META = {
    "D-FON-01": {
        "atlas": "ДАРЯ",
        "question_type": "ДАРЯ: фонетика",
        "question": "Произношение согласного /г/ в интервокальной позиции",
        "num": "1",
    },
    "D-FON-02": {
        "atlas": "ДАРЯ",
        "question_type": "ДАРЯ: фонетика",
        "question": "Тип безударного вокализма после твёрдых согласных",
        "num": "2",
    },
    "D-MOR-01": {
        "atlas": "ДАРЯ",
        "question_type": "ДАРЯ: морфология",
        "question": "Окончание 3 л. мн. ч. настоящего времени",
        "num": "3",
    },
    "L-NAT-01": {
        "atlas": "ЛАРНГ",
        "question_type": "ЛАРНГ: лексика / природа",
        "question": "Название открытого места в лесу",
        "num": "1",
    },
    "L-NAT-02": {
        "atlas": "ЛАРНГ",
        "question_type": "ЛАРНГ: лексика / природа",
        "question": "Название заболоченного места",
        "num": "2",
    },
    "L-MAT-01": {
        "atlas": "ЛАРНГ",
        "question_type": "ЛАРНГ: лексика / материальная культура",
        "question": "Название традиционного сельского дома",
        "num": "3",
    },
}

FALLBACK_COORDS = {
    "дебесы": (57.6500, 53.8167),
    "шаркан": (57.2978, 53.8658),
    "селты": (57.3097, 52.1358),
    "грахово": (56.0447, 51.9553),
}

GIS_SYSTEMS = [
    {
        "ГИС": "QGIS",
        "Назначение": "Свободная настольная ГИС для редактирования, анализа и публикации карт.",
        "Что удобно для атласа": "Лёгкая работа с CSV, GeoJSON, Shapefile, подписями и тематическими стилями.",
        "Форматы": "GeoJSON, GeoPackage, Shapefile, CSV, WMS/WFS и др.",
        "Интерфейс": "Настольный.",
    },
    {
        "ГИС": "ArcGIS Online",
        "Назначение": "Веб-платформа для публикации карт и совместной работы.",
        "Что удобно для атласа": "Быстрое размещение интерактивных карт и слоёв для экспедиционных данных.",
        "Форматы": "Hosted layers, CSV, GeoJSON, Shapefile.",
        "Интерфейс": "Веб.",
    },
    {
        "ГИС": "Google Earth Pro",
        "Назначение": "Визуализация точек, маршрутов и простых тематических слоёв.",
        "Что удобно для атласа": "Быстрая проверка полевых маршрутов и точек на спутниковой подложке.",
        "Форматы": "KML/KMZ, CSV.",
        "Интерфейс": "Настольный.",
    },
    {
        "ГИС": "Google My Maps",
        "Назначение": "Простой веб-инструмент для общедоступных карт.",
        "Что удобно для атласа": "Лёгкая совместная разметка населённых пунктов и маршрутов.",
        "Форматы": "KML, CSV, таблицы Google.",
        "Интерфейс": "Веб.",
    },
    {
        "ГИС": "MapInfo Pro",
        "Назначение": "Профессиональная настольная ГИС для картографии и анализа.",
        "Что удобно для атласа": "Тематические карты, легенды, печатные макеты и экспорт.",
        "Форматы": "TAB, Shapefile, GeoJSON, CSV.",
        "Интерфейс": "Настольный.",
    },
    {
        "ГИС": "ГИС Аксиома",
        "Назначение": "Российская ГИС-платформа для корпоративных и ведомственных задач.",
        "Что удобно для атласа": "Хранение слоёв и справочников, публикация ведомственных карт.",
        "Форматы": "Векторные слои, таблицы, обменные форматы.",
        "Интерфейс": "Настольный / корпоративный.",
    },
    {
        "ГИС": "ГИС Панорама",
        "Назначение": "Российская профессиональная ГИС для топографических и ведомственных данных.",
        "Что удобно для атласа": "Работа с топоосновой, пространственным анализом и экспортом слоёв.",
        "Форматы": "SXF/TX, MIF/MID, Shapefile, GeoTIFF, CSV и др.",
        "Интерфейс": "Настольный и серверные компоненты.",
    },
    {
        "ГИС": "NextGIS",
        "Назначение": "Веб-ГИС и инструменты публикации карт.",
        "Что удобно для атласа": "Публикация районов, ареалов и совместная работа с веб-слоями.",
        "Форматы": "GeoJSON, GeoPackage, Shapefile, WMS/WFS, CSV.",
        "Интерфейс": "Веб + мобильные и настольные инструменты.",
    },
    {
        "ГИС": "ГИС ИНТЕГРО",
        "Назначение": "ГИС для интеграции пространственных и тематических данных.",
        "Что удобно для атласа": "Комплексное хранение, ведомственная аналитика и единые справочники.",
        "Форматы": "Зависят от конфигурации и модулей.",
        "Интерфейс": "Настольный / корпоративный.",
    },
]

ALIASES = {
    "регион": "region",
    "край": "region",
    "республика": "region",
    "область": "region",
    "область / край / республика": "region",
    "region": "region",
    "район": "district",
    "district": "district",
    "муниципальный район": "district",
    "населенный пункт": "settlement",
    "населённый пункт": "settlement",
    "н.п.": "settlement",
    "settlement": "settlement",
    "тип населенного пункта": "settlement_type",
    "тип населённого пункта": "settlement_type",
    "settlement_type": "settlement_type",
    "широта": "latitude",
    "latitude": "latitude",
    "lat": "latitude",
    "долгота": "longitude",
    "longitude": "longitude",
    "lon": "longitude",
    "lng": "longitude",
    "ландшафт": "landscape",
    "landscape": "landscape",
    "атлас": "atlas_system",
    "atlas": "atlas_system",
    "источник вопросника": "atlas_system",
    "atlas_system": "atlas_system",
    "тип вопроса": "question_type",
    "раздел вопроса": "question_type",
    "question_type": "question_type",
    "код вопроса": "question_id",
    "номер вопроса": "question_id",
    "question_id": "question_id",
    "вопрос": "question",
    "question": "question",
    "комментарий": "comment",
    "примечание": "comment",
    "comment": "comment",
    "источник": "source",
    "source": "source",
    "год": "year",
    "year": "year",
}

MAP_CENTER = [56.95, 52.85]


def page_setup() -> None:
    st.set_page_config(
        page_title="Интерактивный атлас русских говоров Удмуртии",
        page_icon="🗺️",
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
            --success-soft: #ecfdf5;
            --warning-soft: #fff7ed;
        }
        .stApp {
            background: linear-gradient(180deg, var(--app-bg) 0%, #ffffff 100%) !important;
            color: var(--text-main) !important;
        }
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            background: transparent !important;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
            border-right: 1px solid var(--border-soft) !important;
        }
        h1, h2, h3, h4, h5, h6, p, li, label, span {
            color: var(--text-main) !important;
            text-shadow: none !important;
        }
        .hero {
            position: relative;
            isolation: isolate;
            overflow: hidden;
            padding: 22px 24px;
            border-radius: 22px;
            background: #ffffff !important;
            border: 1px solid var(--border-soft);
            box-shadow: 0 1px 14px rgba(15, 23, 42, .06);
            margin-bottom: 18px;
        }
        .hero::before {
            content: "";
            position: absolute;
            inset: 0;
            z-index: -1;
            background:
                radial-gradient(circle at 12% 20%, rgba(37, 99, 235, .08), transparent 30%),
                radial-gradient(circle at 88% 0%, rgba(14, 165, 233, .08), transparent 28%);
        }
        .hero h1 {
            margin: 0;
            font-size: 2.1rem;
            line-height: 1.18;
        }
        .hero p {
            margin: 8px 0 0 0;
            color: var(--text-muted) !important;
            line-height: 1.55;
        }
        .card {
            background: #ffffff;
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 1px 10px rgba(15, 23, 42, .05);
            margin-bottom: 14px;
        }
        .soft-card {
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
        }
        .inline-badge {
            display: inline-block;
            padding: 4px 9px;
            border-radius: 999px;
            background: var(--accent-soft);
            color: #075985 !important;
            font-size: 0.84rem;
            font-weight: 600;
            margin: 0 6px 6px 0;
        }
        .table-wrap {
            background: #ffffff;
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 1px 10px rgba(15, 23, 42, .05);
        }
        .table-wrap table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 0.93rem;
        }
        .table-wrap th {
            background: #eff6ff;
            color: #1e3a8a !important;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-soft);
        }
        .table-wrap td {
            padding: 10px 12px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: top;
            word-wrap: break-word;
            white-space: normal;
        }
        .table-wrap tr:nth-child(even) td {
            background: #fcfdff;
        }
        .note-box {
            background: var(--success-soft);
            border: 1px solid #ccebdc;
            border-radius: 14px;
            padding: 12px 14px;
            color: #14532d !important;
            margin-bottom: 12px;
        }
        .warn-box {
            background: var(--warning-soft);
            border: 1px solid #fed7aa;
            border-radius: 14px;
            padding: 12px 14px;
            color: #9a3412 !important;
            margin-bottom: 12px;
        }
        .legend-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin: 0 14px 10px 0;
            font-size: 0.9rem;
        }
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 999px;
            display: inline-block;
            border: 1px solid rgba(15,23,42,.12);
        }
        .small-muted {
            color: var(--text-muted) !important;
            font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def empty_dataset() -> pd.DataFrame:
    return pd.DataFrame(columns=ALL_COLUMNS)


def clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def alias_key(name: str) -> str:
    return clean_text(name).lower().replace("ё", "е")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return empty_dataset()
    renamed: dict[str, str] = {}
    for col in df.columns:
        key = alias_key(str(col))
        if key in ALIASES:
            renamed[col] = ALIASES[key]
            continue
        unit_match = re.search(r"(?:linguistic[_ ]*unit|единиц[аы]?|вариант)[ _-]?(\d)", key)
        if unit_match:
            renamed[col] = f"linguistic_unit_{unit_match.group(1)}"
            continue
        if key in {"linguistic_unit", "единица", "единицы", "вариант"}:
            renamed[col] = "linguistic_unit_1"
    df = df.rename(columns=renamed).copy()
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[ALL_COLUMNS].copy()


def unique_join(values: Iterable[object], sep: str = "; ") -> str:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = clean_text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return sep.join(result)


def normalize_search_text(text: object) -> str:
    return clean_text(text).lower().replace("ё", "е")


def split_units(raw: object) -> list[str]:
    text = clean_text(raw)
    if not text:
        return []
    parts: list[str] = []
    for chunk in re.split(r"[;\n]+", text):
        item = clean_text(chunk)
        if item:
            parts.append(item)
    return parts[:3]


def combine_units(row: pd.Series) -> str:
    values: list[str] = []
    for col in ["linguistic_unit_1", "linguistic_unit_2", "linguistic_unit_3"]:
        item = clean_text(row.get(col, ""))
        if item:
            values.append(item)
    return " • ".join(dict.fromkeys(values))


@st.cache_data(show_spinner=False)
def load_sample_data() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DATA_PATH)


@st.cache_data(show_spinner=False)
def load_template_data() -> pd.DataFrame:
    return pd.read_csv(TEMPLATE_DATA_PATH)


@st.cache_data(show_spinner=False)
def load_url_csv(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    if df.empty:
        return df

    for col in [
        "region",
        "district",
        "settlement",
        "settlement_type",
        "landscape",
        "atlas_system",
        "question_type",
        "question_id",
        "question",
        "comment",
        "source",
    ]:
        df[col] = df[col].map(clean_text)

    for col in ["linguistic_unit_1", "linguistic_unit_2", "linguistic_unit_3"]:
        df[col] = df[col].map(clean_text)

    df["atlas_system"] = df["atlas_system"].replace({"даря": "ДАРЯ", "ларнг": "ЛАРНГ"})
    df["atlas_system"] = df["atlas_system"].apply(
        lambda value: QUESTION_META.get(clean_text(value), {}).get("atlas", value)
    )

    df["question_id"] = df["question_id"].map(clean_text)
    supported_ids = {item for values in QUESTION_SELECTION.values() for item in values}
    df = df[df["question_id"].isin(supported_ids)].copy()

    if df.empty:
        return empty_dataset()

    df["atlas_system"] = df["question_id"].map(lambda qid: QUESTION_META[qid]["atlas"])
    df["question_type"] = df["question_id"].map(lambda qid: QUESTION_META[qid]["question_type"])
    df["question"] = df["question_id"].map(lambda qid: QUESTION_META[qid]["question"])
    df["question_num"] = df["question_id"].map(lambda qid: QUESTION_META[qid]["num"])

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna("")

    city_mask = df["settlement_type"].str.contains("город", case=False, na=False)
    df = df.loc[~city_mask].copy()

    df["unit_display"] = df.apply(combine_units, axis=1)
    df["unit_display"] = df["unit_display"].replace("", "—")
    search_cols = [
        "region",
        "district",
        "settlement",
        "settlement_type",
        "landscape",
        "atlas_system",
        "question_type",
        "question_id",
        "question",
        "unit_display",
        "comment",
    ]
    df["search_blob"] = df[search_cols].fillna("").astype(str).agg(" | ".join, axis=1).map(normalize_search_text)
    df = df.sort_values(["atlas_system", "question_num", "region", "district", "settlement"]).reset_index(drop=True)
    return df


def get_data_source() -> pd.DataFrame:
    with st.sidebar:
        st.markdown("### Данные")
        source_mode = st.radio(
            "Источник",
            ["Демо-данные", "Загрузить CSV", "Ссылка на CSV"],
            label_visibility="collapsed",
        )

        df: pd.DataFrame | None = None
        if source_mode == "Демо-данные":
            df = load_sample_data()
        elif source_mode == "Загрузить CSV":
            uploaded = st.file_uploader("CSV-файл", type=["csv"])
            if uploaded is not None:
                df = pd.read_csv(uploaded)
            else:
                st.info("Загрузите CSV или переключитесь на демо-данные.")
        else:
            url = st.text_input(
                "Прямая ссылка на CSV",
                placeholder="https://.../export?format=csv",
            )
            if url:
                try:
                    df = load_url_csv(url)
                except Exception as exc:
                    st.error(f"Не удалось загрузить CSV по ссылке: {exc}")
            else:
                st.info("Вставьте ссылку на CSV-файл или на экспорт Google Sheets в формате CSV.")

        template_csv = TEMPLATE_DATA_PATH.read_bytes()
        st.download_button(
            "Скачать шаблон CSV",
            data=template_csv,
            file_name="data_template.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if df is None:
        df = load_sample_data()
    return prepare_dataset(df)


def stable_rgb(label: str) -> tuple[int, int, int]:
    digest = hashlib.md5(label.encode("utf-8")).hexdigest()
    hue = int(digest[:8], 16) / 0xFFFFFFFF
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.58, 0.88)
    return int(red * 255), int(green * 255), int(blue * 255)


def rgb_hex(label: str) -> str:
    red, green, blue = stable_rgb(label)
    return f"#{red:02x}{green:02x}{blue:02x}"


def explode_units(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if df.empty:
        return pd.DataFrame(columns=["atlas_system", "question_id", "question_num", "question", "unit", "latitude", "longitude", "settlement"])
    for _, row in df.iterrows():
        units: list[str] = []
        for col in ["linguistic_unit_1", "linguistic_unit_2", "linguistic_unit_3"]:
            units.extend(split_units(row.get(col, "")))
        units = list(dict.fromkeys(units))
        if not units:
            continue
        for unit in units:
            rows.append(
                {
                    "atlas_system": row["atlas_system"],
                    "question_id": row["question_id"],
                    "question_num": row["question_num"],
                    "question": row["question"],
                    "unit": unit,
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "settlement": row["settlement"],
                }
            )
    return pd.DataFrame(rows)


def convex_hull_path(points: list[tuple[float, float]]) -> list[list[float]] | None:
    unique_points = sorted({(round(lon, 6), round(lat, 6)) for lon, lat in points})
    if len(unique_points) < 3:
        return None
    hull_source = pd.DataFrame(unique_points, columns=["lon", "lat"])
    try:
        hull = ConvexHull(hull_source[["lon", "lat"]].to_numpy())
    except QhullError:
        return None
    polygon = [[float(hull_source.iloc[idx]["lat"]), float(hull_source.iloc[idx]["lon"])] for idx in hull.vertices]
    if polygon:
        polygon.append(polygon[0])
    return polygon or None


def line_path(points: list[tuple[float, float]]) -> list[list[float]]:
    ordered = sorted({(round(lon, 6), round(lat, 6)) for lon, lat in points})
    return [[lat, lon] for lon, lat in ordered]


def build_map_shapes(df: pd.DataFrame) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    exploded = explode_units(df)
    if exploded.empty:
        return [], []

    areals: list[dict[str, object]] = []
    isoglosses: list[dict[str, object]] = []
    grouped = exploded.groupby(["atlas_system", "question_id", "question_num", "question", "unit"], dropna=False)

    for (atlas, question_id, question_num, question, unit), group in grouped:
        coords = list(zip(group["longitude"].astype(float), group["latitude"].astype(float)))
        unique_points = sorted({(round(lon, 6), round(lat, 6)) for lon, lat in coords})
        if len(unique_points) < 2:
            continue
        label = f"{question_id}:{unit}"
        color = rgb_hex(label)
        polyline = line_path(coords)
        polygon = convex_hull_path(coords)
        isoglosses.append(
            {
                "atlas": atlas,
                "question_id": question_id,
                "question_num": question_num,
                "question": question,
                "unit": unit,
                "count": len({clean_text(v) for v in group["settlement"] if clean_text(v)}),
                "path": polygon or polyline,
                "color": color,
            }
        )
        if polygon:
            areals.append(
                {
                    "atlas": atlas,
                    "question_id": question_id,
                    "question_num": question_num,
                    "question": question,
                    "unit": unit,
                    "count": len({clean_text(v) for v in group["settlement"] if clean_text(v)}),
                    "polygon": polygon,
                    "color": color,
                }
            )
    areals.sort(key=lambda item: (-int(item["count"]), str(item["question_id"]), str(item["unit"])))
    isoglosses.sort(key=lambda item: (-int(item["count"]), str(item["question_id"]), str(item["unit"])))
    return areals, isoglosses


def aggregate_points(df: pd.DataFrame, direct_settlements: set[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    direct_settlements = direct_settlements or set()
    valid = df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty:
        return pd.DataFrame()
    grouped = (
        valid.groupby(["region", "district", "settlement", "latitude", "longitude"], dropna=False)
        .agg(
            settlement_type=("settlement_type", "first"),
            landscape=("landscape", "first"),
            atlas_system=("atlas_system", unique_join),
            question_nums=("question_num", unique_join),
            questions=("question", unique_join),
            units=("unit_display", unique_join),
            comments=("comment", unique_join),
            record_count=("question_id", "size"),
        )
        .reset_index()
    )
    grouped["direct_match"] = grouped["settlement"].isin(direct_settlements)
    return grouped.sort_values(["district", "settlement"]).reset_index(drop=True)


def fit_bounds_from_points(points_df: pd.DataFrame) -> list[list[float]] | None:
    if points_df.empty:
        return None
    return [
        [float(points_df["latitude"].min()), float(points_df["longitude"].min())],
        [float(points_df["latitude"].max()), float(points_df["longitude"].max())],
    ]


def build_leaflet_map(display_df: pd.DataFrame, direct_df: pd.DataFrame, show_related: bool) -> tuple[folium.Map, int, int, int]:
    points_df = aggregate_points(display_df, set(direct_df["settlement"].unique()) if not direct_df.empty else set())
    areals, isoglosses = build_map_shapes(display_df)

    if points_df.empty:
        fmap = folium.Map(location=MAP_CENTER, zoom_start=7, tiles="CartoDB positron", control_scale=True)
        return fmap, 0, 0, 0

    center = [float(points_df["latitude"].mean()), float(points_df["longitude"].mean())]
    fmap = folium.Map(location=center, zoom_start=7, tiles="CartoDB positron", control_scale=True, prefer_canvas=True)
    Fullscreen(position="topright").add_to(fmap)
    try:
        Geocoder(collapsed=True, add_marker=False).add_to(fmap)
    except Exception:
        pass

    points_layer = folium.FeatureGroup(name="Населённые пункты", show=True)
    for _, row in points_df.iterrows():
        landscape_label = clean_text(row["landscape"]) or "не указан"
        point_color = rgb_hex(f"landscape:{landscape_label}")
        radius = 7 if bool(row["direct_match"]) else 5
        weight = 3 if bool(row["direct_match"]) else 1
        popup_html = (
            f"<b>{html.escape(clean_text(row['settlement']))}</b><br>"
            f"{html.escape(clean_text(row['district']))}, {html.escape(clean_text(row['region']))}<br>"
            f"<b>Тип:</b> {html.escape(clean_text(row['settlement_type']) or '—')}<br>"
            f"<b>Ландшафт:</b> {html.escape(clean_text(row['landscape']) or '—')}<br>"
            f"<b>Вопросы:</b> {html.escape(clean_text(row['question_nums']) or '—')}<br>"
            f"<b>Единицы:</b> {html.escape(clean_text(row['units']) or '—')}<br>"
            f"<b>Комментарий:</b> {html.escape(clean_text(row['comments']) or '—')}"
        )
        folium.CircleMarker(
            location=[float(row["latitude"]), float(row["longitude"])],
            radius=radius,
            color=point_color,
            fill=True,
            fill_color=point_color,
            fill_opacity=0.82,
            weight=weight,
            tooltip=clean_text(row["settlement"]),
            popup=folium.Popup(popup_html, max_width=380),
        ).add_to(points_layer)
    points_layer.add_to(fmap)

    areal_layer = folium.FeatureGroup(name="Ареалы", show=True)
    for item in areals:
        folium.Polygon(
            locations=item["polygon"],
            color=item["color"],
            weight=2,
            fill=True,
            fill_color=item["color"],
            fill_opacity=0.18,
            tooltip=(
                f"{item['atlas']} • вопрос {item['question_num']} • {item['unit']} "
                f"({item['count']} н. п.)"
            ),
        ).add_to(areal_layer)
    areal_layer.add_to(fmap)

    isogloss_layer = folium.FeatureGroup(name="Изоглоссы", show=True)
    for item in isoglosses:
        folium.PolyLine(
            locations=item["path"],
            color=item["color"],
            weight=3,
            opacity=0.8,
            tooltip=(
                f"{item['atlas']} • вопрос {item['question_num']} • {item['unit']} "
                f"({item['count']} н. п.)"
            ),
        ).add_to(isogloss_layer)
    isogloss_layer.add_to(fmap)

    if show_related:
        folium.LayerControl(collapsed=False).add_to(fmap)

    bounds = fit_bounds_from_points(points_df)
    if bounds:
        fmap.fit_bounds(bounds, padding=(24, 24))
    return fmap, len(areals), len(isoglosses), len(points_df)


def build_search_mask(df: pd.DataFrame, query: str) -> pd.Series:
    tokens = [token for token in normalize_search_text(query).split() if token]
    if not tokens:
        return pd.Series(True, index=df.index)
    mask = pd.Series(True, index=df.index)
    for token in tokens:
        mask &= df["search_blob"].str.contains(token, regex=False, na=False)
    return mask


def filter_dataset(
    df: pd.DataFrame,
    regions: list[str],
    districts: list[str],
    atlases: list[str],
    question_types: list[str],
    query: str,
    show_related: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object] | None]:
    filtered = df.copy()
    if regions:
        filtered = filtered[filtered["region"].isin(regions)]
    if districts:
        filtered = filtered[filtered["district"].isin(districts)]
    if atlases:
        filtered = filtered[filtered["atlas_system"].isin(atlases)]
    if question_types:
        filtered = filtered[filtered["question_type"].isin(question_types)]

    info: dict[str, object] | None = None
    direct = filtered.copy()
    if clean_text(query):
        direct = filtered[build_search_mask(filtered, query)].copy()
        if direct.empty:
            return direct, direct, {
                "query": clean_text(query),
                "direct_rows": 0,
                "expanded_rows": 0,
                "question_ids": [],
                "settlements": [],
            }
        if show_related:
            related_questions = sorted(direct["question_id"].dropna().unique().tolist())
            related_settlements = sorted(direct["settlement"].dropna().unique().tolist())
            expanded = filtered[
                filtered["question_id"].isin(related_questions)
                | filtered["settlement"].isin(related_settlements)
            ].copy()
        else:
            expanded = direct.copy()
        info = {
            "query": clean_text(query),
            "direct_rows": int(len(direct)),
            "expanded_rows": int(len(expanded)),
            "question_ids": sorted(direct["question_id"].dropna().unique().tolist()),
            "settlements": sorted(direct["settlement"].dropna().unique().tolist()),
        }
        return direct, expanded, info
    return direct, filtered, info


def metric_row(df: pd.DataFrame) -> None:
    points = df["settlement"].nunique()
    questions = df["question_id"].nunique()
    units = explode_units(df)["unit"].nunique() if not df.empty else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Населённые пункты", points)
    col2.metric("Вопросы", questions)
    col3.metric("Единицы", units)
    col4.metric("Записи", len(df))


def render_question_cards(df: pd.DataFrame) -> None:
    for atlas in ["ДАРЯ", "ЛАРНГ"]:
        atlas_df = df[df["atlas_system"] == atlas]
        st.markdown(f"#### {atlas}")
        badges = []
        for qid in QUESTION_SELECTION[atlas]:
            meta = QUESTION_META[qid]
            used = int((atlas_df["question_id"] == qid).sum())
            badges.append(
                f"<span class='inline-badge'>Вопрос {meta['num']}: {html.escape(meta['question'])} · записей {used}</span>"
            )
        st.markdown("<div class='soft-card'>" + "".join(badges) + "</div>", unsafe_allow_html=True)


def legend_html(df: pd.DataFrame) -> str:
    points_df = aggregate_points(df)
    if points_df.empty:
        return ""
    values = sorted(points_df["landscape"].dropna().astype(str).unique().tolist())[:8]
    chunks: list[str] = []
    for value in values:
        color = rgb_hex(f"landscape:{value}")
        chunks.append(
            "<span class='legend-chip'><span class='legend-color' style='background:{}'></span>{}</span>".format(
                color,
                html.escape(value or "не указан"),
            )
        )
    return "".join(chunks)


def escape_cell(value: object) -> str:
    text = clean_text(value) or "—"
    text = html.escape(text).replace("\n", "<br>")
    return text


def render_html_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Нет данных для отображения.")
        return
    safe = df.copy()
    for col in safe.columns:
        safe[col] = safe[col].map(escape_cell)
    html_table = safe.to_html(index=False, escape=False)
    st.markdown(f"<div class='table-wrap'>{html_table}</div>", unsafe_allow_html=True)


def build_matrix_table(df: pd.DataFrame, atlas: str) -> pd.DataFrame:
    subset = df[df["atlas_system"] == atlas].copy()
    if subset.empty:
        return pd.DataFrame(columns=["Населённый пункт", "Район", "Тип", "Ландшафт", "1", "2", "3"])
    pivot_source = (
        subset.groupby(
            ["settlement", "district", "settlement_type", "landscape", "question_num"],
            dropna=False,
        )["unit_display"]
        .apply(unique_join)
        .reset_index()
    )
    matrix = pivot_source.pivot_table(
        index=["settlement", "district", "settlement_type", "landscape"],
        columns="question_num",
        values="unit_display",
        aggfunc=unique_join,
        fill_value="—",
    ).reset_index()
    for col in ["1", "2", "3"]:
        if col not in matrix.columns:
            matrix[col] = "—"
    matrix = matrix[["settlement", "district", "settlement_type", "landscape", "1", "2", "3"]].copy()
    matrix.columns = ["Населённый пункт", "Район", "Тип", "Ландшафт", "1", "2", "3"]
    matrix = matrix.sort_values(["Район", "Населённый пункт"]).reset_index(drop=True)
    return matrix


def build_detail_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Атлас", "№", "Вопрос", "Единицы", "Населённый пункт", "Район", "Комментарий"])
    detail = df[["atlas_system", "question_num", "question", "unit_display", "settlement", "district", "comment"]].copy()
    detail.columns = ["Атлас", "№", "Вопрос", "Единицы", "Населённый пункт", "Район", "Комментарий"]
    return detail.sort_values(["Атлас", "№", "Район", "Населённый пункт"]).reset_index(drop=True)


def build_points_table(df: pd.DataFrame) -> pd.DataFrame:
    points = aggregate_points(df)
    if points.empty:
        return pd.DataFrame(columns=["Населённый пункт", "Район", "Тип", "Ландшафт", "Широта", "Долгота", "Вопросы"])
    table = points[["settlement", "district", "settlement_type", "landscape", "latitude", "longitude", "question_nums"]].copy()
    table.columns = ["Населённый пункт", "Район", "Тип", "Ландшафт", "Широта", "Долгота", "Вопросы"]
    return table.reset_index(drop=True)


def question_legend_table(atlas: str) -> pd.DataFrame:
    rows = []
    for qid in QUESTION_SELECTION[atlas]:
        meta = QUESTION_META[qid]
        rows.append({"№": meta["num"], "Вопрос": meta["question"], "Раздел": meta["question_type"]})
    return pd.DataFrame(rows)


def parse_float(value: object) -> float | None:
    text = clean_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def find_coordinates(name: str, district: str, region: str, df: pd.DataFrame) -> tuple[float | None, float | None, str]:
    normalized_name = normalize_search_text(name)
    if not normalized_name:
        return None, None, "Введите название населённого пункта."

    existing = df[df["settlement"].map(normalize_search_text) == normalized_name].dropna(subset=["latitude", "longitude"])
    if not existing.empty:
        first = existing.iloc[0]
        return float(first["latitude"]), float(first["longitude"]), "Координаты взяты из уже имеющихся данных."

    if normalized_name in FALLBACK_COORDS:
        lat, lon = FALLBACK_COORDS[normalized_name]
        return lat, lon, "Координаты найдены во встроенном справочнике приложения."

    geolocator = Nominatim(user_agent="udmurt-dialect-atlas-leaflet-app")
    queries = [
        ", ".join([part for part in [name, district, region, "Россия"] if clean_text(part)]),
        ", ".join([part for part in [name, region, "Россия"] if clean_text(part)]),
        ", ".join([part for part in [name, "Россия"] if clean_text(part)]),
    ]
    for query in queries:
        try:
            location = geolocator.geocode(query, timeout=10)
        except (GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable):
            location = None
        if location is not None:
            return float(location.latitude), float(location.longitude), f"Координаты найдены автоматически: {query}."
    return None, None, "Не удалось подобрать координаты автоматически. Проверьте написание или задайте координаты вручную."


def build_added_rows(
    region: str,
    district: str,
    settlement: str,
    settlement_type: str,
    latitude: float,
    longitude: float,
    landscape: str,
    comment: str,
    answers: dict[str, str],
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for question_id, answer_text in answers.items():
        units = split_units(answer_text)
        if not units:
            continue
        meta = QUESTION_META[question_id]
        record = {
            "region": clean_text(region),
            "district": clean_text(district),
            "settlement": clean_text(settlement),
            "settlement_type": clean_text(settlement_type),
            "latitude": latitude,
            "longitude": longitude,
            "landscape": clean_text(landscape),
            "atlas_system": meta["atlas"],
            "question_type": meta["question_type"],
            "question_id": question_id,
            "question": meta["question"],
            "linguistic_unit_1": units[0] if len(units) > 0 else "",
            "linguistic_unit_2": units[1] if len(units) > 1 else "",
            "linguistic_unit_3": units[2] if len(units) > 2 else "",
            "comment": clean_text(comment),
            "source": "добавлено через интерфейс",
            "year": 2026,
        }
        records.append(record)
    if not records:
        return empty_dataset()
    return pd.DataFrame(records, columns=ALL_COLUMNS)


def ensure_session_state() -> None:
    if "user_rows" not in st.session_state:
        st.session_state.user_rows = empty_dataset()
    defaults = {
        "new_region": "Удмуртская Республика",
        "new_district": "",
        "new_settlement": "",
        "new_settlement_type": "село",
        "new_landscape": "",
        "new_latitude": "",
        "new_longitude": "",
        "new_comment": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    for question_id, meta in QUESTION_META.items():
        answer_key = f"answer_{question_id}"
        if answer_key not in st.session_state:
            st.session_state[answer_key] = ""


def render_sidebar_filters(df: pd.DataFrame) -> tuple[list[str], list[str], list[str], list[str], str, bool]:
    with st.sidebar:
        st.divider()
        st.markdown("### Фильтры")
        search_query = st.text_input(
            "Поиск",
            placeholder="Населённый пункт, район, вопрос, единица...",
        )
        show_related = st.toggle(
            "Показывать связанные ареалы и изоглоссы",
            value=True,
            help="При поиске карта расширяет выборку по найденным вопросам и населённым пунктам, чтобы на любой запрос строились ареалы и изоглоссы.",
        )
        regions = sorted(df["region"].dropna().astype(str).unique().tolist())
        districts = sorted(df["district"].dropna().astype(str).unique().tolist())
        atlases = sorted(df["atlas_system"].dropna().astype(str).unique().tolist())
        question_types = sorted(df["question_type"].dropna().astype(str).unique().tolist())
        selected_regions = st.multiselect("Регион", regions)
        selected_districts = st.multiselect("Район", districts)
        selected_atlases = st.multiselect("Атлас", atlases)
        selected_question_types = st.multiselect("Раздел вопроса", question_types)
    return (
        selected_regions,
        selected_districts,
        selected_atlases,
        selected_question_types,
        search_query,
        show_related,
    )


def render_intro(df: pd.DataFrame) -> None:
    added_settlements = ["Дебёсы", "Шаркан", "Селты", "Грахово"]
    st.markdown(
        """
        <div class="hero">
            <h1>Интерактивный атлас русских говоров Удмуртии</h1>
            <p>
                Версия на Leaflet: города убраны из точечного слоя, оставлены остальные населённые пункты,
                таблица сокращена до 3 вопросов ДАРЯ и 3 вопросов ЛАРНГ, а поиск разворачивает карту так,
                чтобы по любому запросу были видны ареалы и изоглоссы.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_row(df)
    st.markdown(
        "<div class='note-box'><b>Что изменено:</b> из демо-данных убраны города; добавлены пункты Дебёсы, Шаркан, Селты и Грахово; карта работает на Leaflet; в таблицах скрыты атлас, год и источник; коды вопросов заменены на 1–3 внутри каждого атласа.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='small-muted'>Добавленные населённые пункты по умолчанию: {}</div>".format(
            ", ".join(added_settlements)
        ),
        unsafe_allow_html=True,
    )


def render_atlas_tab(df: pd.DataFrame) -> None:
    st.markdown("### Набор вопросов")
    render_question_cards(df)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ДАРЯ — легенда вопросов")
        render_html_table(question_legend_table("ДАРЯ"))
    with col2:
        st.markdown("#### ЛАРНГ — легенда вопросов")
        render_html_table(question_legend_table("ЛАРНГ"))


def render_map_tab(display_df: pd.DataFrame, direct_df: pd.DataFrame, search_info: dict[str, object] | None, show_related: bool) -> None:
    st.markdown("### Карта ареалов, изоглосс и населённых пунктов")
    if search_info is not None:
        if int(search_info["direct_rows"]) > 0:
            st.markdown(
                (
                    "<div class='note-box'><b>Поиск:</b> «{}». Прямых совпадений: {}. "
                    "Строк на карте после расширения контекста: {}. "
                    "Связанные вопросы: {}.</div>"
                ).format(
                    html.escape(str(search_info["query"])),
                    search_info["direct_rows"],
                    search_info["expanded_rows"],
                    html.escape(", ".join(search_info["question_ids"]) or "—"),
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='warn-box'><b>Поиск:</b> совпадений не найдено. Попробуйте другой запрос.</div>",
                unsafe_allow_html=True,
            )

    fmap, areal_count, isogloss_count, point_count = build_leaflet_map(display_df, direct_df, show_related)
    map_col, info_col = st.columns([4.2, 1.4])
    with map_col:
        st_folium(fmap, height=620, use_container_width=True)
    with info_col:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("#### Слои")
        st.write(f"Населённые пункты: **{point_count}**")
        st.write(f"Ареалы: **{areal_count}**")
        st.write(f"Изоглоссы: **{isogloss_count}**")
        st.markdown("<div class='small-muted'>Точки отображают населённые пункты без городов. Поиск может расширять выборку по связанным вопросам и пунктам.</div>", unsafe_allow_html=True)
        legend = legend_html(display_df)
        if legend:
            st.markdown("#### Ландшафты")
            st.markdown(legend, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_points_tab(df: pd.DataFrame, base_df: pd.DataFrame) -> None:
    st.markdown("### Населённые пункты")
    subtab1, subtab2 = st.tabs(["Список пунктов", "Добавить пункт"])
    with subtab1:
        render_html_table(build_points_table(df))
    with subtab2:
        st.markdown(
            "<div class='small-muted'>Координаты можно получить автоматически по названию населённого пункта, району и региону. Если пункт уже есть в наборе, координаты будут взяты из данных; иначе приложение попробует подобрать их через геокодирование.</div>",
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Регион", key="new_region")
            st.text_input("Район", key="new_district")
            st.text_input("Населённый пункт", key="new_settlement")
            st.selectbox("Тип населённого пункта", ["село", "посёлок", "деревня", "станция", "слобода"], key="new_settlement_type")
            st.text_input("Ландшафт", key="new_landscape")
        with col2:
            st.text_input("Широта", key="new_latitude")
            st.text_input("Долгота", key="new_longitude")
            st.text_area("Комментарий", key="new_comment", height=120)
            if st.button("Найти координаты автоматически", use_container_width=True):
                full_df = prepare_dataset(pd.concat([base_df, st.session_state.user_rows], ignore_index=True))
                lat, lon, message = find_coordinates(
                    st.session_state.new_settlement,
                    st.session_state.new_district,
                    st.session_state.new_region,
                    full_df,
                )
                if lat is not None and lon is not None:
                    st.session_state.new_latitude = f"{lat:.6f}"
                    st.session_state.new_longitude = f"{lon:.6f}"
                    st.success(message)
                else:
                    st.warning(message)
        st.markdown("#### Ответы по 6 вопросам")
        answer_tabs = st.tabs(["ДАРЯ", "ЛАРНГ"])
        with answer_tabs[0]:
            for question_id in QUESTION_SELECTION["ДАРЯ"]:
                meta = QUESTION_META[question_id]
                st.text_input(
                    f"Вопрос {meta['num']}: {meta['question']}",
                    key=f"answer_{question_id}",
                    placeholder="Несколько вариантов можно разделять точкой с запятой",
                )
        with answer_tabs[1]:
            for question_id in QUESTION_SELECTION["ЛАРНГ"]:
                meta = QUESTION_META[question_id]
                st.text_input(
                    f"Вопрос {meta['num']}: {meta['question']}",
                    key=f"answer_{question_id}",
                    placeholder="Несколько вариантов можно разделять точкой с запятой",
                )
        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            if st.button("Добавить населённый пункт", type="primary", use_container_width=True):
                settlement = clean_text(st.session_state.new_settlement)
                district = clean_text(st.session_state.new_district)
                region = clean_text(st.session_state.new_region)
                settlement_type = clean_text(st.session_state.new_settlement_type)
                landscape = clean_text(st.session_state.new_landscape)
                comment = clean_text(st.session_state.new_comment)
                latitude = parse_float(st.session_state.new_latitude)
                longitude = parse_float(st.session_state.new_longitude)
                answers = {question_id: st.session_state[f"answer_{question_id}"] for question_id in QUESTION_META}
                if not settlement:
                    st.error("Укажите населённый пункт.")
                elif latitude is None or longitude is None:
                    st.error("Укажите или найдите координаты.")
                else:
                    new_rows = build_added_rows(
                        region=region,
                        district=district,
                        settlement=settlement,
                        settlement_type=settlement_type,
                        latitude=latitude,
                        longitude=longitude,
                        landscape=landscape,
                        comment=comment,
                        answers=answers,
                    )
                    if new_rows.empty:
                        st.error("Заполните хотя бы один ответ по вопросам ДАРЯ или ЛАРНГ.")
                    else:
                        st.session_state.user_rows = pd.concat([st.session_state.user_rows, new_rows], ignore_index=True)
                        st.success(f"Населённый пункт «{settlement}» добавлен в текущую сессию.")
        with action_col2:
            if st.button("Сбросить добавленные записи", use_container_width=True):
                st.session_state.user_rows = empty_dataset()
                st.success("Добавленные в текущей сессии записи удалены.")

        current_df = prepare_dataset(pd.concat([base_df, st.session_state.user_rows], ignore_index=True))
        st.download_button(
            "Скачать текущий CSV с добавлениями",
            data=current_df[ALL_COLUMNS].to_csv(index=False).encode("utf-8-sig"),
            file_name="sample_dialects_leaflet_current.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_units_tab(df: pd.DataFrame) -> None:
    st.markdown("### Единицы и записи")
    detail = build_detail_table(df)
    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "№": st.column_config.TextColumn(width="small"),
            "Вопрос": st.column_config.TextColumn(width="large"),
            "Единицы": st.column_config.TextColumn(width="large"),
            "Комментарий": st.column_config.TextColumn(width="large"),
        },
    )


def render_table_tab(df: pd.DataFrame) -> None:
    st.markdown("### Сводные таблицы")
    table_tabs = st.tabs(["ДАРЯ", "ЛАРНГ"])
    for atlas, tab in zip(["ДАРЯ", "ЛАРНГ"], table_tabs):
        with tab:
            st.markdown(
                "<div class='small-muted'>В таблице оставлены только аккуратные поля: населённый пункт, район, тип, ландшафт и ответы на вопросы 1–3. Атлас, год и источник убраны из отображения.</div>",
                unsafe_allow_html=True,
            )
            legend = question_legend_table(atlas)
            render_html_table(legend)
            st.markdown("#### Таблица ответов")
            render_html_table(build_matrix_table(df, atlas))


def render_gis_tab() -> None:
    st.markdown("### Подходящие ГИС-системы")
    gis_df = pd.DataFrame(GIS_SYSTEMS)
    st.dataframe(gis_df, use_container_width=True, hide_index=True, height=420)


def render_help_tab() -> None:
    st.markdown("### Инструкция")
    st.markdown(
        """
        <div class='card'>
            <p><b>1.</b> В боковой панели выберите источник данных: демо-набор, загрузка CSV или ссылка на CSV.</p>
            <p><b>2.</b> Поиск работает по населённым пунктам, районам, вопросам, единицам и комментариям.</p>
            <p><b>3.</b> Если включён переключатель «Показывать связанные ареалы и изоглоссы», карта расширяет результаты поиска по связанным вопросам и населённым пунктам.</p>
            <p><b>4.</b> Вкладка «Пункты» позволяет добавить новый населённый пункт, автоматически подобрать координаты и скачать обновлённый CSV.</p>
            <p><b>5.</b> Во вкладке «Таблица» коды вопросов сокращены до 1–3 внутри каждого атласа, чтобы матрица была компактной и аккуратной.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    page_setup()
    ensure_session_state()

    base_df = get_data_source()
    current_df = prepare_dataset(pd.concat([base_df, st.session_state.user_rows], ignore_index=True))

    render_intro(current_df)

    (
        selected_regions,
        selected_districts,
        selected_atlases,
        selected_question_types,
        search_query,
        show_related,
    ) = render_sidebar_filters(current_df)

    direct_df, display_df, search_info = filter_dataset(
        current_df,
        regions=selected_regions,
        districts=selected_districts,
        atlases=selected_atlases,
        question_types=selected_question_types,
        query=search_query,
        show_related=show_related,
    )

    tabs = st.tabs(["Атлас", "Карты", "Пункты", "Единицы", "Таблица", "ГИС", "Инструкция"])
    with tabs[0]:
        render_atlas_tab(current_df)
    with tabs[1]:
        render_map_tab(display_df, direct_df, search_info, show_related)
    with tabs[2]:
        render_points_tab(current_df, base_df)
    with tabs[3]:
        render_units_tab(display_df if clean_text(search_query) else current_df)
    with tabs[4]:
        render_table_tab(display_df if clean_text(search_query) else current_df)
    with tabs[5]:
        render_gis_tab()
    with tabs[6]:
        render_help_tab()


if __name__ == "__main__":
    main()
