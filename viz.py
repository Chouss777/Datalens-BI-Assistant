"""Choose a Plotly chart from a query result's data types."""

from datetime import date, datetime
from numbers import Number

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


def auto_chart(df):
    """Return a Plotly figure, or None for an empty result."""
    if df.empty:
        return None

    data = df.dropna(axis="columns", how="all").copy()
    if data.empty:
        return None

    dates, numbers, categories = [], [], []
    for column in data:
        series = data[column]
        values = series.dropna()
        if is_datetime64_any_dtype(series) or values.map(lambda value: isinstance(value, (date, datetime))).all():
            dates.append(column)
        elif not is_bool_dtype(series) and (
            is_numeric_dtype(series)
            or values.map(lambda value: isinstance(value, Number) and not isinstance(value, bool)).all()
        ):
            name = str(column).lower()
            if name != "id" and not name.endswith("_id"):
                numbers.append(column)
                data[column] = pd.to_numeric(series)
        else:
            categories.append(column)
            data[column] = series.astype("string")

    if numbers and len(data) == 1:
        metric = numbers[0]
        return go.Figure(go.Indicator(mode="number", value=float(data[metric].iloc[0]), title={"text": metric}))

    if dates and numbers:
        x, y = dates[0], numbers[0]
        color = next((column for column in categories if 2 <= data[column].nunique() <= 10), None)
        if color is not None and not data[color].notna().all():
            color = None
        series_keys = [x, color] if color is not None else [x]
        points = data.dropna(subset=[x, y]).sort_values(x)
        if points.empty:
            return None
        if points.duplicated(series_keys).any():
            return px.scatter(points, x=x, y=y, color=color, title=f"{y} selon {x}")
        return px.line(points, x=x, y=y, color=color, markers=True, title=f"{y} selon {x}")

    if categories and numbers:
        x = next((column for column in categories if data[column].nunique() > 1), categories[0])
        y = numbers[0]
        points = data.dropna(subset=[x, y])
        if points.empty:
            return None
        if points[x].is_unique and len(points) <= 40:
            return px.bar(points, x=x, y=y, title=f"{y} par {x}")
        if points[x].nunique() <= 20:
            return px.box(points, x=x, y=y, points="all", title=f"Distribution de {y} par {x}")
        if len(numbers) >= 2:
            return px.scatter(data, x=numbers[0], y=numbers[1], hover_name=x)
        return px.histogram(points, x=y, title=f"Distribution de {y}")

    if len(numbers) >= 2:
        return px.scatter(data, x=numbers[0], y=numbers[1])
    if numbers:
        return px.histogram(data, x=numbers[0], title=f"Distribution de {numbers[0]}")
    if dates or categories:
        column = (dates or categories)[0]
        counts = data[column].value_counts().head(30).rename_axis("valeur").reset_index(name="observations")
        if dates:
            counts = counts.sort_values("valeur")
        return px.bar(counts, x="valeur", y="observations", labels={"valeur": column},
                      title=f"Nombre de lignes par {column}")
    return None
