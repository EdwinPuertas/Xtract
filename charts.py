"""Construcción de gráficas de línea (SVG) para la vista /trends.

No usa ninguna librería de gráficos externa: genera coordenadas de líneas SVG
directamente a partir de las corridas guardadas en trends_store, para poder
graficar sin JavaScript ni dependencias adicionales en el front-end.

Los colores de las 8 emociones son la paleta categórica de referencia del
skill de dataviz de Claude (8 tonos validados contra ceguera al color y
contraste en modo claro/oscuro); se referencian aquí solo por nombre de
variable CSS — los valores hex viven en static/style.css (--emo-1..--emo-8),
con su variante de modo oscuro en el mismo archivo.
"""

CHART_WIDTH = 640
CHART_HEIGHT = 220
PAD = 30

SENTIMENT_KEYS = [
    ("positivo", "Positivo", "var(--sent-pos)"),
    ("neutral", "Neutral", "var(--sent-neu)"),
    ("negativo", "Negativo", "var(--sent-neg)"),
]

# Orden fijo (nunca ciclado) sobre las 8 variables CSS validadas por el
# validador de paleta del skill de dataviz.
EMOTION_KEYS = [
    ("alegría", "Alegría", "var(--emo-1)"),
    ("enojo", "Enojo", "var(--emo-2)"),
    ("calma", "Calma", "var(--emo-3)"),
    ("sorpresa", "Sorpresa", "var(--emo-4)"),
    ("alivio", "Alivio", "var(--emo-5)"),
    ("aburrimiento", "Aburrimiento", "var(--emo-6)"),
    ("miedo", "Miedo", "var(--emo-7)"),
    ("tristeza", "Tristeza", "var(--emo-8)"),
]


def _fmt_date(run_at) -> str:
    if isinstance(run_at, str):
        return run_at[:10]
    return run_at.strftime("%Y-%m-%d")


def _scale_x(i: int, n: int) -> float:
    if n <= 1:
        return CHART_WIDTH / 2
    return PAD + (CHART_WIDTH - 2 * PAD) * i / (n - 1)


def _scale_y(value: float, vmax: float) -> float:
    vmax = vmax or 1
    return PAD + (CHART_HEIGHT - 2 * PAD) * (1 - value / vmax)


def _build_line_chart(dates: list[str], keys: list[tuple[str, str, str]], series_values: dict[str, list[float]]) -> dict:
    n = len(dates)
    all_values = [v for values in series_values.values() for v in values]
    vmax = max(all_values) if all_values else 0
    vmax = vmax if vmax > 0 else 100  # eje 0-100% por defecto cuando aún no hay datos

    series = []
    for key, label, color in keys:
        values = series_values.get(key, [])
        points = [(_scale_x(i, n), _scale_y(v, vmax)) for i, v in enumerate(values)]
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points) if points else ""
        series.append(
            {
                "key": key,
                "label": label,
                "color": color,
                "path": path,
                "points": [
                    {"x": x, "y": y, "value": v, "date": dates[i]} for i, ((x, y), v) in enumerate(zip(points, values))
                ],
            }
        )

    gridlines = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        value = vmax * frac
        gridlines.append({"y": round(_scale_y(value, vmax), 1), "label": f"{value:.0f}%"})

    return {
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
        "pad": PAD,
        "dates": dates,
        "vmax": round(vmax, 2),
        "series": series,
        "gridlines": gridlines,
    }


def build_sentiment_chart(runs: list[dict]) -> dict:
    """runs: lista de corridas en orden ascendente por fecha (ver
    trends_store.get_recent_runs), cada una con `run_at` y `nlp.sentiment_summary`."""
    dates = [_fmt_date(r["run_at"]) for r in runs]
    keys = [k for k, _, _ in SENTIMENT_KEYS]
    series_values: dict[str, list[float]] = {k: [] for k in keys}

    for r in runs:
        summary = (r.get("nlp") or {}).get("sentiment_summary") or {}
        total = sum(summary.get(k, 0) for k in keys) or 1
        for k in keys:
            series_values[k].append(round(100 * summary.get(k, 0) / total, 1))

    return _build_line_chart(dates, SENTIMENT_KEYS, series_values)


def build_emotion_chart(runs: list[dict]) -> dict:
    """runs: igual que build_sentiment_chart, usando `nlp.vad_summary.emotion_counts`."""
    dates = [_fmt_date(r["run_at"]) for r in runs]
    keys = [k for k, _, _ in EMOTION_KEYS]
    series_values: dict[str, list[float]] = {k: [] for k in keys}

    for r in runs:
        vad_summary = (r.get("nlp") or {}).get("vad_summary") or {}
        counts = vad_summary.get("emotion_counts") or {}
        total = sum(counts.get(k, 0) for k in keys) or 1
        for k in keys:
            series_values[k].append(round(100 * counts.get(k, 0) / total, 1))

    return _build_line_chart(dates, EMOTION_KEYS, series_values)
