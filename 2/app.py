from __future__ import annotations

import colorsys
import hashlib
import html
import json
import math
import re
import time
from io import StringIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import pydeck as pdk
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
SAMPLE_DATA_PATH = DATA_DIR / "sample_dialects.csv"
TEMPLATE_DATA_PATH = DATA_DIR / "data_template.csv"
MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

DARYA_QUESTIONS = [
    {
        "atlas_system": "ДАРЯ",
        "question_id": "1",
        "question_type": "ДАРЯ: фонетика",
        "question": "Произношение согласного /г/ в интервокальной позиции",
        "old_ids": {"D-FON-01"},
    },
    {
        "atlas_system": "ДАРЯ",
        "question_id": "2",
        "question_type": "ДАРЯ: фонетика",
        "question": "Тип безударного вокализма после твёрдых согласных",
        "old_ids": {"D-FON-02"},
    },
    {
        "atlas_system": "ДАРЯ",
        "question_id": "3",
        "question_type": "ДАРЯ: морфология",
        "question": "Окончание 3 л. мн. ч. настоящего времени",
        "old_ids": {"D-MOR-01"},
    },
]

LARNG_QUESTIONS = [
    {
        "atlas_system": "ЛАРНГ",
        "question_id": "1",
        "question_type": "ЛАРНГ: лексика / природа",
        "question": "Название открытого места в лесу",
        "old_ids": {"L-NAT-01"},
    },
    {
        "atlas_system": "ЛАРНГ",
        "question_id": "2",
        "question_type": "ЛАРНГ: лексика / природа",
        "question": "Название сильного дождя",
        "old_ids": {"L-NAT-02"},
    },
    {
        "atlas_system": "ЛАРНГ",
        "question_id": "3",
        "question_type": "ЛАРНГ: лексика / материальная культура",
        "question": "Название традиционного сельского дома",
        "old_ids": {"L-MAT-01"},
    },
]

QUESTION_LIBRARY = DARYA_QUESTIONS + LARNG_QUESTIONS
OLD_ID_TO_QUESTION = {old: item for item in QUESTION_LIBRARY for old in item["old_ids"]}
QUESTION_TEXT_TO_QUESTION = {item["question"].lower(): item for item in QUESTION_LIBRARY}

CANONICAL_COLUMNS = [
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

DISPLAY_COLUMNS = [
    "question_id",
    "region",
    "district",
    "settlement",
    "settlement_type",
    "latitude",
    "longitude",
    "landscape",
    "question_type",
    "question",
    "linguistic_unit_1",
    "linguistic_unit_2",
    "linguistic_unit_3",
    "unit_display",
    "comment",
]

DISPLAY_LABELS = {
    "question_id": "№ вопроса",
    "region": "Регион",
    "district": "Район",
    "settlement": "Населённый пункт",
    "settlement_type": "Тип",
    "latitude": "Широта",
    "longitude": "Долгота",
    "landscape": "Ландшафт",
    "question_type": "Раздел",
    "question": "Вопрос",
    "linguistic_unit_1": "Единица 1",
    "linguistic_unit_2": "Единица 2",
    "linguistic_unit_3": "Единица 3",
    "unit_display": "Все единицы",
    "comment": "Комментарий",
}

ALIASES = {
    "регион": "region",
    "область": "region",
    "край": "region",
    "республика": "region",
    "область / край / республика": "region",
    "область/край/республика": "region",
    "region": "region",
    "район": "district",
    "муниципальный район": "district",
    "district": "district",
    "населенный пункт": "settlement",
    "населённый пункт": "settlement",
    "н.п.": "settlement",
    "нп": "settlement",
    "settlement": "settlement",
    "тип населенного пункта": "settlement_type",
    "тип населённого пункта": "settlement_type",
    "settlement_type": "settlement_type",
    "широта": "latitude",
    "lat": "latitude",
    "latitude": "latitude",
    "долгота": "longitude",
    "lon": "longitude",
    "lng": "longitude",
    "longitude": "longitude",
    "ландшафт": "landscape",
    "landscape": "landscape",
    "атлас": "atlas_system",
    "источник вопросника": "atlas_system",
    "atlas": "atlas_system",
    "atlas_system": "atlas_system",
    "тип вопроса": "question_type",
    "раздел вопроса": "question_type",
    "question_type": "question_type",
    "код вопроса": "question_id",
    "номер вопроса": "question_id",
    "№ вопроса": "question_id",
    "question_id": "question_id",
    "вопрос": "question",
    "question": "question",
    "лингвистическая единица 1": "linguistic_unit_1",
    "лингвистическая единица 2": "linguistic_unit_2",
    "лингвистическая единица 3": "linguistic_unit_3",
    "единица 1": "linguistic_unit_1",
    "единица 2": "linguistic_unit_2",
    "единица 3": "linguistic_unit_3",
    "комментарий": "comment",
    "примечание": "comment",
    "comment": "comment",
    "источник": "source",
    "source": "source",
    "год": "year",
    "year": "year",
}

FALLBACK_CSV = """region,district,settlement,settlement_type,latitude,longitude,landscape,atlas_system,question_type,question_id,question,linguistic_unit_1,linguistic_unit_2,linguistic_unit_3,comment
Удмуртская Республика,Кезский район,Кез,посёлок,57.8951,53.7133,северная лесная зона,ДАРЯ,ДАРЯ: фонетика,1,Произношение согласного /г/ в интервокальной позиции,[g] взрывной,,,демонстрационная строка
Удмуртская Республика,Кезский район,Кез,посёлок,57.8951,53.7133,северная лесная зона,ЛАРНГ,ЛАРНГ: лексика / природа,1,Название открытого места в лесу,ляда,,,демонстрационная строка
"""


def _clean_name(name: object) -> str:
    text = str(name).strip().replace("\n", " ")
    return re.sub(r"\s+", " ", text)


def _alias_key(name: object) -> str:
    return _clean_name(name).lower().replace("ё", "е")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed: dict[str, str] = {}
    for col in df.columns:
        clean = _clean_name(col)
        key = _alias_key(clean)
        unit_match = re.match(
            r"^(лингвистическая\s+единица|единица|ответ|variant|unit|linguistic_unit)[ _-]*(\d+)$",
            key,
        )
        if unit_match:
            renamed[col] = f"linguistic_unit_{unit_match.group(2)}"
        elif key in ALIASES:
            renamed[col] = ALIASES[key]
        else:
            renamed[col] = clean
    return df.rename(columns=renamed)


def get_linguistic_columns(df: pd.DataFrame) -> list[str]:
    cols = [col for col in df.columns if re.match(r"^linguistic_unit_\d+$", str(col))]
    return sorted(cols, key=lambda col: int(str(col).rsplit("_", 1)[1]))


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df).copy()
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    text_cols = [col for col in CANONICAL_COLUMNS if col not in {"latitude", "longitude"}]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in get_linguistic_columns(df):
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["atlas_system"] = df["atlas_system"].replace({"": "не указан"})
    df["question_type"] = df["question_type"].replace({"": "не указан"})
    df["landscape"] = df["landscape"].replace({"": "не указан"})
    return df


def normalize_question_catalog(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df).copy()

    for idx, row in df.iterrows():
        raw_id = str(row.get("question_id", "")).strip()
        raw_question = str(row.get("question", "")).strip()
        raw_atlas = str(row.get("atlas_system", "")).strip().upper()

        item = None
        if raw_id in OLD_ID_TO_QUESTION:
            item = OLD_ID_TO_QUESTION[raw_id]
        elif raw_question.lower() in QUESTION_TEXT_TO_QUESTION:
            item = QUESTION_TEXT_TO_QUESTION[raw_question.lower()]
        elif raw_id in {"1", "2", "3"}:
            pool = DARYA_QUESTIONS if "ДАР" in raw_atlas else LARNG_QUESTIONS if "ЛАР" in raw_atlas else []
            item = next((q for q in pool if q["question_id"] == raw_id), None)

        if item:
            df.at[idx, "atlas_system"] = item["atlas_system"]
            df.at[idx, "question_id"] = item["question_id"]
            df.at[idx, "question_type"] = item["question_type"]
            df.at[idx, "question"] = item["question"]

    allowed = {
        (item["atlas_system"], item["question_id"], item["question"])
        for item in QUESTION_LIBRARY
    }
    mask = df.apply(
        lambda row: (row["atlas_system"], str(row["question_id"]), row["question"]) in allowed,
        axis=1,
    )
    return df[mask].copy()


def remove_city_settlements(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df)
    type_text = df["settlement_type"].fillna("").astype(str).str.lower()
    district_text = df["district"].fillna("").astype(str).str.lower()
    settlement_text = df["settlement"].fillna("").astype(str).str.lower()
    city_mask = (
        type_text.str.contains(r"\bгород\b|\bг\.\b", regex=True)
        | district_text.str.match(r"^г\.\s*")
        | settlement_text.str.startswith("г. ")
    )
    return df[~city_mask].copy()


def split_units(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [part.strip() for part in re.split(r";|,|\|", str(value)) if part and part.strip()]


def row_units(row: pd.Series, unit_cols: Iterable[str] | None = None) -> list[str]:
    if unit_cols is None:
        unit_cols = [c for c in row.index if re.match(r"^linguistic_unit_\d+$", str(c))]
    units: list[str] = []
    for col in unit_cols:
        units.extend(split_units(row.get(col, "")))

    seen: set[str] = set()
    result: list[str] = []
    for unit in units:
        key = unit.lower()
        if key not in seen:
            seen.add(key)
            result.append(unit)
    return result


def add_unit_display(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df).copy()
    unit_cols = get_linguistic_columns(df)
    df["unit_display"] = df.apply(lambda row: "; ".join(row_units(row, unit_cols)), axis=1)
    df["unit_display"] = df["unit_display"].replace({"": "нет данных"})
    return df


def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df)
    df = remove_city_settlements(df)
    df = normalize_question_catalog(df)
    df = add_unit_display(df)
    return df.reset_index(drop=True)


def read_csv_bytes(content: bytes, sep: str | None = None) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text = content.decode(encoding)
            return pd.read_csv(StringIO(text), sep=sep or None, engine="python")
        except Exception:
            continue
    raise ValueError("Не удалось прочитать CSV. Проверьте кодировку UTF-8/CP1251 и разделитель.")


def read_csv_path(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception:
            continue
    raise ValueError(f"Не удалось прочитать файл: {path}")


def secret_value(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


@st.cache_data(show_spinner=False)
def read_csv_url(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


def load_initial_data() -> pd.DataFrame:
    data_url = secret_value("DATA_CSV_URL")
    if data_url:
        try:
            return read_csv_url(data_url)
        except Exception as exc:
            st.warning(f"Не удалось загрузить DATA_CSV_URL, открыта локальная демо-таблица: {exc}")

    if SAMPLE_DATA_PATH.exists():
        return read_csv_path(SAMPLE_DATA_PATH)
    return pd.read_csv(StringIO(FALLBACK_CSV))


def to_download_csv(df: pd.DataFrame, display_only: bool = False) -> bytes:
    if display_only:
        return make_display_table(df).to_csv(index=False).encode("utf-8-sig")
    cols = [col for col in CANONICAL_COLUMNS if col in df.columns]
    return df[cols].to_csv(index=False).encode("utf-8-sig")


def label_color(label: object, alpha: int = 190) -> list[int]:
    text = str(label or "нет данных").encode("utf-8")
    digest = hashlib.md5(text).hexdigest()
    hue = int(digest[:6], 16) / 0xFFFFFF
    r, g, b = colorsys.hls_to_rgb(hue, 0.50, 0.58)
    return [int(r * 255), int(g * 255), int(b * 255), alpha]


def label_color_hex(label: object) -> str:
    r, g, b, _ = label_color(label)
    return f"#{r:02x}{g:02x}{b:02x}"


def _cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def convex_hull(points: Iterable[tuple[float, float]]) -> list[list[float]]:
    pts = sorted(set(points))
    if len(pts) < 3:
        return []

    lower: list[tuple[float, float]] = []
    for point in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return []
    closed = hull + [hull[0]]
    return [[float(lon), float(lat)] for lon, lat in closed]


def circle_polygon(lon: float, lat: float, radius_km: float = 8.0, steps: int = 36) -> list[list[float]]:
    lat_radius = radius_km / 111.0
    lon_radius = radius_km / max(111.0 * math.cos(math.radians(lat)), 1e-6)
    points: list[list[float]] = []
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        points.append([float(lon + lon_radius * math.cos(angle)), float(lat + lat_radius * math.sin(angle))])
    return points


def padded_hull(points: list[tuple[float, float]], pad_km: float = 8.0) -> list[list[float]]:
    unique = sorted(set(points))
    if not unique:
        return []
    if len(unique) == 1:
        lon, lat = unique[0]
        return circle_polygon(lon, lat, radius_km=pad_km)

    padded: list[tuple[float, float]] = []
    for lon, lat in unique:
        lat_pad = pad_km / 111.0
        lon_pad = pad_km / max(111.0 * math.cos(math.radians(lat)), 1e-6)
        padded.extend(
            [
                (lon - lon_pad, lat - lat_pad),
                (lon - lon_pad, lat + lat_pad),
                (lon + lon_pad, lat - lat_pad),
                (lon + lon_pad, lat + lat_pad),
            ]
        )
    return convex_hull(padded)


def map_view_state(df: pd.DataFrame) -> dict[str, float]:
    valid = df.dropna(subset=["latitude", "longitude"])
    if valid.empty:
        return {"latitude": 57.1, "longitude": 53.2, "zoom": 6.4, "pitch": 0}

    lat_min, lat_max = valid["latitude"].min(), valid["latitude"].max()
    lon_min, lon_max = valid["longitude"].min(), valid["longitude"].max()
    span = max(float(lat_max - lat_min), float(lon_max - lon_min), 0.2)
    if span > 5:
        zoom = 5.5
    elif span > 2.5:
        zoom = 6.0
    elif span > 1:
        zoom = 7.0
    else:
        zoom = 8.4
    return {
        "latitude": float((lat_min + lat_max) / 2),
        "longitude": float((lon_min + lon_max) / 2),
        "zoom": zoom,
        "pitch": 0,
    }


def explode_units(df: pd.DataFrame) -> pd.DataFrame:
    df = add_unit_display(df)
    unit_cols = get_linguistic_columns(df)
    records: list[dict] = []
    for _, row in df.iterrows():
        units = row_units(row, unit_cols) or ["нет данных"]
        for unit in units:
            item = row.to_dict()
            item["linguistic_unit"] = unit
            records.append(item)
    return pd.DataFrame(records)


def build_areals(exploded_df: pd.DataFrame, group_col: str = "linguistic_unit") -> list[dict]:
    valid = exploded_df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty or group_col not in valid.columns:
        return []

    areals: list[dict] = []
    for label, group in valid.groupby(group_col, dropna=False):
        points = list(zip(group["longitude"].astype(float), group["latitude"].astype(float)))
        polygon = convex_hull(points) or padded_hull(points)
        if len(polygon) < 4:
            continue
        color = label_color(label, alpha=26)
        areals.append(
            {
                "label": str(label),
                "polygon": polygon,
                "path": polygon,
                "count": int(group["settlement"].nunique()),
                "fill_color": color,
                "line_color": [color[0], color[1], color[2], 150],
                "tooltip": f"<b>Ареал:</b> {html.escape(str(label))}<br/><b>Пунктов:</b> {int(group['settlement'].nunique())}",
            }
        )
    return sorted(areals, key=lambda item: (-item["count"], item["label"]))


def build_isoglosses(exploded_df: pd.DataFrame, group_col: str = "linguistic_unit") -> list[dict]:
    valid = exploded_df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty or group_col not in valid.columns:
        return []

    paths: list[dict] = []
    for label, group in valid.groupby(group_col, dropna=False):
        points = sorted(set(zip(group["longitude"].astype(float), group["latitude"].astype(float))))
        if not points:
            continue
        path = convex_hull(points)
        if not path:
            if len(points) == 1:
                path = circle_polygon(points[0][0], points[0][1], radius_km=5.0)
            else:
                path = [[float(lon), float(lat)] for lon, lat in points]
        color = label_color(label, alpha=230)
        paths.append(
            {
                "label": str(label),
                "path": path,
                "line_color": [color[0], color[1], color[2], 230],
                "count": int(group["settlement"].nunique()),
                "tooltip": f"<b>Изоглосса:</b> {html.escape(str(label))}<br/><b>Пунктов:</b> {int(group['settlement'].nunique())}",
            }
        )
    return sorted(paths, key=lambda item: (-item["count"], item["label"]))


def unique_join(series: pd.Series, limit: int = 9) -> str:
    values: list[str] = []
    for value in series.dropna().astype(str):
        for item in value.split(";"):
            item = item.strip()
            if item and item not in values:
                values.append(item)
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; +{len(values) - limit}"
    return "; ".join(shown) + suffix


def aggregate_points(df: pd.DataFrame, color_mode: str) -> pd.DataFrame:
    valid = add_unit_display(df).dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty:
        return pd.DataFrame()

    grouped = (
        valid.groupby(["region", "district", "settlement", "settlement_type", "latitude", "longitude"], dropna=False)
        .agg(
            landscape=("landscape", "first"),
            question_type=("question_type", unique_join),
            question_label=("question", unique_join),
            unit_display=("unit_display", unique_join),
            comments=("comment", unique_join),
            record_count=("question", "size"),
            question_count=("question", "nunique"),
        )
        .reset_index()
    )

    if color_mode == "Ландшафт":
        grouped["color_label"] = grouped["landscape"].replace("", "не указан")
    elif color_mode == "Раздел вопроса":
        grouped["color_label"] = grouped["question_type"].replace("", "не указан")
    else:
        grouped["color_label"] = grouped["unit_display"].replace("", "нет данных")

    grouped["color"] = grouped["color_label"].apply(lambda value: label_color(value, alpha=215))
    grouped["outline_color"] = grouped["color_label"].apply(lambda value: label_color(value, alpha=255))
    grouped["radius_m"] = 4500 + grouped["record_count"].clip(0, 10).astype(int) * 350
    grouped["short_label"] = grouped["settlement"].astype(str).str.slice(0, 18)
    grouped["tooltip"] = grouped.apply(
        lambda row: (
            f"<b>{html.escape(str(row['settlement']))}</b><br/>"
            f"{html.escape(str(row['district']))}, {html.escape(str(row['region']))}<br/>"
            f"<b>Тип:</b> {html.escape(str(row['settlement_type']))}<br/>"
            f"<b>Ландшафт:</b> {html.escape(str(row['landscape']))}<br/>"
            f"<b>Вопросы:</b> {html.escape(str(row['question_label']))}<br/>"
            f"<b>Единицы:</b> {html.escape(str(row['unit_display']))}<br/>"
            f"<b>Комментарий:</b> {html.escape(str(row['comments'] or '—'))}"
        ),
        axis=1,
    )
    return grouped


def build_region_outlines(df: pd.DataFrame) -> list[dict]:
    valid = df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty:
        return []

    outlines: list[dict] = []
    for region, group in valid.groupby("region", dropna=False):
        points = list(zip(group["longitude"].astype(float), group["latitude"].astype(float)))
        polygon = convex_hull(points) or padded_hull(points, pad_km=20.0)
        if len(polygon) >= 4:
            outlines.append(
                {
                    "region": str(region),
                    "polygon": polygon,
                    "line_color": [70, 70, 70, 220],
                    "tooltip": f"<b>Регион:</b> {html.escape(str(region))}",
                }
            )
    return outlines


@st.cache_data(show_spinner=False)
def load_boundary_geojson(url: str) -> dict | None:
    if not url:
        return None
    req = Request(url, headers={"User-Agent": "udmurt-dialect-map/1.0"})
    with urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def build_deck(
    df: pd.DataFrame,
    color_mode: str,
    show_areals: bool,
    show_isoglosses: bool,
    show_region_outlines: bool,
    show_labels: bool,
) -> tuple[pdk.Deck, dict[str, int]]:
    valid = add_unit_display(df).dropna(subset=["latitude", "longitude"]).copy()
    exploded = explode_units(valid)
    areals = build_areals(exploded) if show_areals else []
    isoglosses = build_isoglosses(exploded) if show_isoglosses else []
    points = aggregate_points(valid, color_mode)
    region_outlines = build_region_outlines(valid) if show_region_outlines else []

    layers: list[pdk.Layer] = []

    boundary_url = secret_value("BOUNDARY_GEOJSON_URL")
    boundary_geojson = None
    if show_region_outlines and boundary_url:
        try:
            boundary_geojson = load_boundary_geojson(boundary_url)
        except Exception as exc:
            st.warning(f"GeoJSON границ не загрузился, использован контур по точкам: {exc}")

    if boundary_geojson:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=boundary_geojson,
                stroked=True,
                filled=False,
                get_line_color=[70, 70, 70, 230],
                line_width_min_pixels=2,
                pickable=True,
            )
        )
    elif region_outlines:
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                data=region_outlines,
                get_polygon="polygon",
                get_fill_color=[0, 0, 0, 0],
                get_line_color="line_color",
                get_line_width=2500,
                line_width_min_pixels=2,
                stroked=True,
                filled=False,
                pickable=True,
            )
        )

    if areals:
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                data=areals,
                get_polygon="polygon",
                get_fill_color="fill_color",
                get_line_color="line_color",
                get_line_width=1200,
                line_width_min_pixels=1,
                stroked=True,
                filled=True,
                pickable=True,
            )
        )

    if isoglosses:
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=isoglosses,
                get_path="path",
                get_color="line_color",
                get_width=1800,
                width_min_pixels=2,
                pickable=True,
            )
        )

    if not points.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=points,
                get_position="[longitude, latitude]",
                get_radius="radius_m",
                get_fill_color="color",
                get_line_color=[255, 255, 255, 240],
                line_width_min_pixels=1,
                stroked=True,
                pickable=True,
            )
        )

        if show_labels:
            layers.append(
                pdk.Layer(
                    "TextLayer",
                    data=points,
                    get_position="[longitude, latitude]",
                    get_text="short_label",
                    get_size=13,
                    get_color=[30, 30, 30, 230],
                    get_angle=0,
                    get_text_anchor="middle",
                    get_alignment_baseline="bottom",
                    pickable=False,
                )
            )

    deck = pdk.Deck(
        map_style=MAP_STYLE,
        initial_view_state=pdk.ViewState(**map_view_state(valid)),
        layers=layers,
        tooltip={"html": "{tooltip}", "style": {"backgroundColor": "white", "color": "#222"}},
    )
    stats = {
        "points": 0 if points.empty else int(points["settlement"].nunique()),
        "records": int(len(valid)),
        "areals": len(areals),
        "isoglosses": len(isoglosses),
        "regions": len(region_outlines) if not boundary_geojson else 1,
    }
    return deck, stats


def filter_dataframe(
    df: pd.DataFrame,
    search_query: str = "",
    regions: list[str] | None = None,
    districts: list[str] | None = None,
    atlas_system: str = "Все",
    question_label: str = "Все вопросы",
) -> pd.DataFrame:
    df = add_unit_display(df)
    result = df.copy()

    if atlas_system != "Все":
        result = result[result["atlas_system"].str.upper().str.contains(atlas_system.upper(), na=False)]
    if regions:
        result = result[result["region"].isin(regions)]
    if districts:
        result = result[result["district"].isin(districts)]
    if question_label != "Все вопросы":
        _, atlas, qid, question = question_label.split("|", 3)
        result = result[
            (result["atlas_system"] == atlas)
            & (result["question_id"].astype(str) == qid)
            & (result["question"] == question)
        ]

    query = search_query.strip().lower()
    if query:
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
        haystack = pd.Series("", index=result.index, dtype="object")
        for col in search_cols:
            haystack = haystack + " " + result[col].fillna("").astype(str)
        result = result[haystack.str.lower().str.contains(re.escape(query), na=False)]

    return result.reset_index(drop=True)


def question_options(df: pd.DataFrame) -> list[tuple[str, str]]:
    options = []
    catalog = (
        df[["atlas_system", "question_id", "question", "question_type"]]
        .drop_duplicates()
        .sort_values(["atlas_system", "question_id"])
    )
    for _, row in catalog.iterrows():
        value = f"q|{row['atlas_system']}|{row['question_id']}|{row['question']}"
        label = f"{row['atlas_system']} {row['question_id']}. {row['question']}"
        options.append((value, label))
    return options


def make_display_table(df: pd.DataFrame) -> pd.DataFrame:
    df = add_unit_display(df).copy()
    cols = [col for col in DISPLAY_COLUMNS if col in df.columns]
    table = df[cols].copy()
    table["latitude"] = table["latitude"].round(6)
    table["longitude"] = table["longitude"].round(6)
    table = table.rename(columns=DISPLAY_LABELS)
    sort_cols = [col for col in ["Регион", "Район", "Населённый пункт", "№ вопроса"] if col in table.columns]
    if sort_cols:
        table = table.sort_values(sort_cols, kind="stable")
    return table.reset_index(drop=True)


def render_table(df: pd.DataFrame) -> None:
    table = make_display_table(df)
    if table.empty:
        st.info("По текущему запросу нет строк для таблицы.")
        return

    height = min(780, 120 + max(1, len(table)) * 58)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=height,
        row_height=64,
        column_config={
            "Вопрос": st.column_config.TextColumn(width="large"),
            "Все единицы": st.column_config.TextColumn(width="large"),
            "Комментарий": st.column_config.TextColumn(width="large"),
            "Ландшафт": st.column_config.TextColumn(width="medium"),
            "Широта": st.column_config.NumberColumn(format="%.6f"),
            "Долгота": st.column_config.NumberColumn(format="%.6f"),
        },
    )
    st.caption(
        "В таблице скрыты служебные поля «атлас», «год» и «источник»; номер вопроса приведён к виду 1, 2, 3 внутри ДАРЯ и ЛАРНГ."
    )


def validate_dataframe(df: pd.DataFrame) -> list[dict[str, str]]:
    df = ensure_columns(df)
    issues: list[dict[str, str]] = []
    required = ["region", "district", "settlement", "question", "question_id"]
    for col in required:
        empty_count = int((df[col].fillna("").astype(str).str.strip() == "").sum())
        if empty_count:
            issues.append({"Уровень": "Ошибка", "Поле": col, "Сообщение": f"Пустых значений: {empty_count}"})

    no_coords = int(df[["latitude", "longitude"]].isna().any(axis=1).sum())
    if no_coords:
        issues.append({"Уровень": "Предупреждение", "Поле": "latitude/longitude", "Сообщение": f"Строк без координат: {no_coords}"})

    city_rows = int(len(ensure_columns(df)) - len(remove_city_settlements(df)))
    if city_rows:
        issues.append({"Уровень": "Информация", "Поле": "settlement_type", "Сообщение": f"Городские строки скрыты с карты и таблицы: {city_rows}"})
    return issues


def geocode_settlement(query: str) -> dict | None:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "ru",
        "accept-language": "ru",
        "addressdetails": 1,
    }
    user_agent = secret_value("NOMINATIM_USER_AGENT", "udmurt-dialect-map-streamlit/1.0")
    req = Request(
        "https://nominatim.openstreetmap.org/search?" + urlencode(params),
        headers={"User-Agent": user_agent},
    )
    with urlopen(req, timeout=12) as response:
        results = json.loads(response.read().decode("utf-8"))
    if not results:
        return None
    first = results[0]
    return {
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "display_name": first.get("display_name", query),
    }


def question_label_lookup() -> dict[str, dict]:
    result = {}
    for item in QUESTION_LIBRARY:
        label = f"{item['atlas_system']} {item['question_id']}. {item['question']}"
        result[label] = item
    return result


def render_add_settlement() -> None:
    st.subheader("Добавить населённый пункт")
    st.write(
        "Координаты можно найти автоматически через OpenStreetMap Nominatim. После добавления скачайте обновлённый CSV и загрузите его в GitHub или Google Sheets."
    )

    for key, value in {
        "add_region": "Удмуртская Республика",
        "add_district": "",
        "add_settlement": "",
        "add_latitude_input": 0.0,
        "add_longitude_input": 0.0,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = value

    col1, col2, col3 = st.columns([1.15, 1, 0.75])
    with col1:
        settlement = st.text_input("Населённый пункт", key="add_settlement")
    with col2:
        district = st.text_input("Район", key="add_district")
    with col3:
        settlement_type = st.selectbox("Тип", ["село", "посёлок", "деревня", "станция", "починок", "иное"])

    region = st.text_input("Регион", key="add_region")
    landscape = st.text_input("Ландшафт / местность", value="не указан")

    if st.button("Найти координаты автоматически"):
        if not settlement.strip():
            st.error("Введите название населённого пункта.")
        else:
            elapsed = time.time() - float(st.session_state.get("_last_geocode_ts", 0.0))
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            query = ", ".join([part for part in [settlement, district, region, "Россия"] if part.strip()])
            try:
                found = geocode_settlement(query)
                st.session_state["_last_geocode_ts"] = time.time()
                if not found:
                    st.warning("Координаты не найдены. Введите широту и долготу вручную.")
                else:
                    st.session_state["add_latitude_input"] = float(found["lat"])
                    st.session_state["add_longitude_input"] = float(found["lon"])
                    st.success(f"Найдено: {found['display_name']}")
            except Exception as exc:
                st.error(f"Ошибка геокодирования: {exc}")

    c1, c2 = st.columns(2)
    with c1:
        latitude = st.number_input("Широта", format="%.6f", key="add_latitude_input")
    with c2:
        longitude = st.number_input("Долгота", format="%.6f", key="add_longitude_input")

    lookup = question_label_lookup()
    labels = list(lookup.keys())
    selected_labels = st.multiselect("Для каких вопросов создать строки", labels, default=labels)
    unit1 = st.text_input("Единица 1 / ответ", value="", key="add_unit1")
    unit2 = st.text_input("Единица 2 / ответ", value="", key="add_unit2")
    unit3 = st.text_input("Единица 3 / ответ", value="", key="add_unit3")
    comment = st.text_area("Комментарий", value="добавлено через форму приложения", height=80)

    if st.button("Добавить в рабочую таблицу"):
        if not settlement.strip() or not district.strip() or not region.strip():
            st.error("Заполните населённый пункт, район и регион.")
            return
        if abs(float(latitude)) < 0.000001 or abs(float(longitude)) < 0.000001:
            st.error("Заполните координаты или выполните автоматический поиск.")
            return
        if not selected_labels:
            st.error("Выберите хотя бы один вопрос.")
            return

        new_rows = []
        for label in selected_labels:
            item = lookup[label]
            new_rows.append(
                {
                    "region": region.strip(),
                    "district": district.strip(),
                    "settlement": settlement.strip(),
                    "settlement_type": settlement_type,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "landscape": landscape.strip() or "не указан",
                    "atlas_system": item["atlas_system"],
                    "question_type": item["question_type"],
                    "question_id": item["question_id"],
                    "question": item["question"],
                    "linguistic_unit_1": unit1.strip(),
                    "linguistic_unit_2": unit2.strip(),
                    "linguistic_unit_3": unit3.strip(),
                    "comment": comment.strip(),
                    "source": "",
                    "year": "",
                }
            )
        current = st.session_state.get("working_df", pd.DataFrame())
        st.session_state["working_df"] = prepare_dataset(pd.concat([ensure_columns(current), pd.DataFrame(new_rows)], ignore_index=True))
        st.success(f"Добавлено строк: {len(new_rows)}. Откройте вкладку «Таблица» и скачайте обновлённый CSV.")


def inject_css() -> None:
    st.markdown(
        """
<style>
.block-container {max-width: 1320px;}
div[data-testid="stDataFrame"] {border: 1px solid #e8e8e8; border-radius: 10px;}
.small-note {font-size: 0.9rem; color: #555;}
</style>
""",
        unsafe_allow_html=True,
    )


def render_instructions() -> None:
    st.subheader("Что изменено")
    st.markdown(
        """
1. Городские точки автоматически скрываются: строки с типом `город` и районы вида `г. ...` не попадают на карту и в таблицу.
2. Поиск работает по населённым пунктам, районам, вопросам, единицам, комментариям и скрытой системе ДАРЯ/ЛАРНГ; для результата сразу строятся точки, ареалы и изоглоссы.
3. В видимой таблице убраны «атлас», «год», «источник»; код вопроса приведён к `1`, `2`, `3`; оставлено 3 вопроса ДАРЯ и 3 вопроса ЛАРНГ.
4. Во вкладке «Добавить пункт» есть автоматический поиск координат по OpenStreetMap Nominatim и ручная правка найденных координат.
5. Границы регионов можно подключить через секрет `BOUNDARY_GEOJSON_URL`. Если GeoJSON не задан, приложение строит технический контур региона по имеющимся точкам.
"""
    )
    st.info(
        "Для точных административных границ лучше загрузить отдельный GeoJSON из QGIS/NextGIS в EPSG:4326 и указать ссылку в Streamlit Secrets."
    )


def main() -> None:
    st.set_page_config(page_title="Карта русских говоров", page_icon="🗺️", layout="wide")
    inject_css()

    st.title("Интерактивная карта русских говоров")
    st.caption("Версия с удалёнными городскими точками, поиском ареалов/изоглосс и аккуратной таблицей.")

    if "working_df" not in st.session_state:
        st.session_state["working_df"] = prepare_dataset(load_initial_data())

    with st.sidebar:
        st.header("Данные и поиск")
        uploaded = st.file_uploader("Загрузить CSV", type=["csv"])
        if uploaded is not None:
            try:
                st.session_state["working_df"] = prepare_dataset(read_csv_bytes(uploaded.getvalue()))
                st.success("CSV загружен.")
            except Exception as exc:
                st.error(f"Не удалось загрузить CSV: {exc}")

        if st.button("Вернуть демо-данные"):
            st.session_state["working_df"] = prepare_dataset(load_initial_data())
            st.cache_data.clear()
            st.rerun()

        df = prepare_dataset(st.session_state["working_df"])
        st.session_state["working_df"] = df

        search_query = st.text_input("Поиск по любому полю", placeholder="например: ляда, Кез, фонетика")
        atlas_system = st.selectbox("Система вопросов", ["Все", "ДАРЯ", "ЛАРНГ"])

        region_options = sorted(df["region"].dropna().unique())
        regions = st.multiselect("Регион", region_options)
        district_source = df[df["region"].isin(regions)] if regions else df
        district_options = sorted(district_source["district"].dropna().unique())
        districts = st.multiselect("Район", district_options)

        q_options = question_options(df)
        labels_by_value = {value: label for value, label in q_options}
        question_values = ["Все вопросы"] + [value for value, _ in q_options]
        question_label = st.selectbox(
            "Вопрос",
            question_values,
            format_func=lambda value: "Все вопросы" if value == "Все вопросы" else labels_by_value.get(value, value),
        )

        color_mode = st.selectbox("Цвет точек", ["Лингвистическая единица", "Ландшафт", "Раздел вопроса"])
        show_areals = st.checkbox("Показывать ареалы", value=True)
        show_isoglosses = st.checkbox("Показывать изоглоссы", value=True)
        show_region_outlines = st.checkbox("Обвести регионы", value=True)
        show_labels = st.checkbox("Подписать пункты", value=False)

    filtered_df = filter_dataframe(df, search_query, regions, districts, atlas_system, question_label)

    tab_map, tab_table, tab_add, tab_info = st.tabs(["Карта", "Таблица", "Добавить пункт", "Инструкция"])

    with tab_map:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Населённых пунктов", int(filtered_df["settlement"].nunique()) if not filtered_df.empty else 0)
        c2.metric("Строк", len(filtered_df))
        c3.metric("Вопросов", int(filtered_df["question"].nunique()) if not filtered_df.empty else 0)
        c4.metric("Единиц", int(explode_units(filtered_df)["linguistic_unit"].nunique()) if not filtered_df.empty else 0)

        if filtered_df.empty:
            st.warning("Поиск не дал результатов. Измените запрос или фильтры.")
        else:
            deck, stats = build_deck(filtered_df, color_mode, show_areals, show_isoglosses, show_region_outlines, show_labels)
            st.pydeck_chart(deck, use_container_width=True, height=690)
            st.caption(
                f"Построено: пунктов — {stats['points']}, ареалов — {stats['areals']}, изоглосс — {stats['isoglosses']}. "
                "Если по запросу найдена только одна точка, ареал и изоглосса показываются как малый контур вокруг неё."
            )

    with tab_table:
        st.subheader("Таблица результатов")
        render_table(filtered_df)
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Скачать отображаемую таблицу CSV",
                data=to_download_csv(filtered_df, display_only=True),
                file_name="dialects_visible_table.csv",
                mime="text/csv",
            )
        with d2:
            st.download_button(
                "Скачать рабочие данные CSV",
                data=to_download_csv(df, display_only=False),
                file_name="sample_dialects_updated.csv",
                mime="text/csv",
            )

        issues = validate_dataframe(st.session_state["working_df"])
        if issues:
            with st.expander("Проверка данных"):
                st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)

    with tab_add:
        render_add_settlement()

    with tab_info:
        render_instructions()


if __name__ == "__main__":
    main()
