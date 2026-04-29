from __future__ import annotations

import colorsys
import hashlib
from typing import Iterable

import pandas as pd


def label_color(label: object, alpha: int = 190) -> list[int]:
    """Stable readable color from any label."""
    text = str(label or "нет данных").encode("utf-8")
    digest = hashlib.md5(text).hexdigest()
    hue = int(digest[:6], 16) / 0xFFFFFF
    # Moderate saturation/lightness keeps text and map readable.
    r, g, b = colorsys.hls_to_rgb(hue, 0.50, 0.58)
    return [int(r * 255), int(g * 255), int(b * 255), alpha]


def label_color_hex(label: object) -> str:
    r, g, b, _ = label_color(label)
    return f"#{r:02x}{g:02x}{b:02x}"


def _cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def convex_hull(points: Iterable[tuple[float, float]]) -> list[list[float]]:
    """Monotonic-chain hull for lon/lat points. Returns a closed polygon."""
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


def map_view_state(df: pd.DataFrame) -> dict[str, float]:
    valid = df.dropna(subset=["latitude", "longitude"])
    if valid.empty:
        return {"latitude": 57.1, "longitude": 53.2, "zoom": 6.5, "pitch": 0}

    lat_min, lat_max = valid["latitude"].min(), valid["latitude"].max()
    lon_min, lon_max = valid["longitude"].min(), valid["longitude"].max()
    lat_span = max(lat_max - lat_min, 0.2)
    lon_span = max(lon_max - lon_min, 0.2)
    span = max(lat_span, lon_span)

    if span > 5:
        zoom = 5.5
    elif span > 2.5:
        zoom = 6.2
    elif span > 1:
        zoom = 7.2
    else:
        zoom = 8.4

    return {
        "latitude": float((lat_min + lat_max) / 2),
        "longitude": float((lon_min + lon_max) / 2),
        "zoom": zoom,
        "pitch": 0,
    }


def build_areals(exploded_df: pd.DataFrame, group_col: str = "linguistic_unit") -> list[dict]:
    valid = exploded_df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty or group_col not in valid.columns:
        return []

    areals: list[dict] = []
    for label, group in valid.groupby(group_col):
        points = list(zip(group["longitude"].astype(float), group["latitude"].astype(float)))
        polygon = convex_hull(points)
        if len(polygon) < 4:
            continue

        color = label_color(label, alpha=24)
        areals.append(
            {
                "label": str(label),
                "polygon": polygon,
                "path": polygon,
                "count": int(group["settlement"].nunique()),
                "fill_color": color,
                "line_color": [color[0], color[1], color[2], 145],
            }
        )

    return sorted(areals, key=lambda item: (-item["count"], item["label"]))


def add_point_visuals(points_df: pd.DataFrame, color_mode: str) -> pd.DataFrame:
    points_df = points_df.copy()

    if color_mode == "Ландшафт":
        points_df["color_label"] = points_df["landscape"].replace("", "не указан")
    elif color_mode == "Тип вопроса":
        points_df["color_label"] = points_df["question_type"].replace("", "не указан")
    elif color_mode == "Атлас":
        points_df["color_label"] = points_df["atlas_system"].replace("", "не указан")
    else:
        points_df["color_label"] = points_df["unit_display"].replace("", "нет данных")

    points_df["color"] = points_df["color_label"].apply(lambda value: label_color(value, alpha=210))
    points_df["outline_color"] = points_df["color_label"].apply(lambda value: label_color(value, alpha=255))
    points_df["radius_m"] = 6500 + points_df["record_count"].clip(0, 10).astype(int) * 700
    points_df["short_label"] = points_df["settlement"].str.slice(0, 18)
    return points_df


def aggregate_points(df: pd.DataFrame) -> pd.DataFrame:
    valid = df.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty:
        return pd.DataFrame()

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

    grouped = (
        valid.groupby(["region", "district", "settlement", "latitude", "longitude"], dropna=False)
        .agg(
            settlement_type=("settlement_type", "first"),
            landscape=("landscape", "first"),
            atlas_system=("atlas_system", unique_join),
            question_type=("question_type", unique_join),
            question_label=("question", unique_join),
            unit_display=("unit_display", unique_join),
            comments=("comment", unique_join),
            record_count=("question", "size"),
            question_count=("question", "nunique"),
        )
        .reset_index()
    )

    grouped["tooltip"] = grouped.apply(
        lambda row: (
            f"<b>{row['settlement']}</b><br/>"
            f"{row['district']}, {row['region']}<br/>"
            f"<b>Ландшафт:</b> {row['landscape']}<br/>"
            f"<b>Вопросы:</b> {row['question_label']}<br/>"
            f"<b>Единицы:</b> {row['unit_display']}<br/>"
            f"<b>Комментарий:</b> {row['comments'] or '—'}"
        ),
        axis=1,
    )

    return grouped
