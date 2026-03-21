#!/usr/bin/env python3
"""Render a minimal explanation-oriented chart card from chart-spec/v1."""

from __future__ import annotations

import argparse
import json
import math
import html
from pathlib import Path


DEFAULT_TOKENS = {
    "bg": "#F8FBF8",
    "surface": "#FFFFFF",
    "text_primary": "#1F2A24",
    "text_secondary": "#5E6C63",
    "accent_medical": "#2F8F6B",
    "accent_soft": "#DFF2EA",
    "line_primary": "#2F8F6B",
    "range_caution": "#F6E7B8",
    "divider": "#D9E6DE",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("chart spec must be a JSON object")
    return data


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render_single_metric_svg(spec: dict) -> str:
    series = spec["series"][0]
    points = [p for p in series.get("points", []) if isinstance(p.get("value"), (int, float))]
    width = 760
    height = 280
    margin_left = 56
    margin_right = 24
    margin_top = 24
    margin_bottom = 42
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    if not points:
        return f'<svg viewBox="0 0 {width} {height}" class="chart-svg"></svg>'

    values = [float(p["value"]) for p in points]
    min_v = min(values)
    max_v = max(values)
    if math.isclose(min_v, max_v):
        pad = max(1.0, abs(min_v) * 0.1 or 1.0)
        min_v -= pad
        max_v += pad
    else:
        pad = (max_v - min_v) * 0.15
        min_v -= pad
        max_v += pad

    def x_at(idx: int) -> float:
        if len(points) == 1:
            return margin_left + plot_w / 2
        return margin_left + idx * (plot_w / (len(points) - 1))

    def y_at(value: float) -> float:
        ratio = (value - min_v) / (max_v - min_v)
        return margin_top + plot_h - ratio * plot_h

    coords = [(x_at(i), y_at(float(point["value"]))) for i, point in enumerate(points)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    band_svg = ""
    for band in spec.get("reference_bands", []):
        upper = band.get("upper")
        lower = band.get("lower")
        color = DEFAULT_TOKENS["range_caution"]
        if isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
            y1 = y_at(float(upper))
            y2 = y_at(float(lower))
            top = min(y1, y2)
            band_svg += (
                f'<rect x="{margin_left}" y="{top:.1f}" width="{plot_w}" '
                f'height="{abs(y2-y1):.1f}" fill="{color}" opacity="0.55" rx="12" />'
            )
        elif isinstance(upper, (int, float)):
            y = y_at(float(upper))
            band_svg += (
                f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left+plot_w}" y2="{y:.1f}" '
                f'stroke="{DEFAULT_TOKENS["text_secondary"]}" stroke-dasharray="6 6" stroke-width="2" />'
                f'<text x="{margin_left+plot_w-4}" y="{y-8:.1f}" text-anchor="end" '
                f'fill="{DEFAULT_TOKENS["text_secondary"]}" font-size="12">{esc(band.get("label"))}</text>'
            )

    point_svg = []
    label_svg = []
    date_svg = []
    for (x, y), point in zip(coords, points):
        point_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{DEFAULT_TOKENS["line_primary"]}" stroke="#fff" stroke-width="3" />'
        )
        label_svg.append(
            f'<text x="{x:.1f}" y="{y-12:.1f}" text-anchor="middle" fill="{DEFAULT_TOKENS["text_primary"]}" font-size="12">{esc(point.get("label") or point.get("value"))}</text>'
        )
        date_svg.append(
            f'<text x="{x:.1f}" y="{height-14}" text-anchor="middle" fill="{DEFAULT_TOKENS["text_secondary"]}" font-size="12">{esc(point.get("date"))}</text>'
        )

    y_ticks = []
    for ratio in [0.0, 0.5, 1.0]:
        value = min_v + (max_v - min_v) * ratio
        y = y_at(value)
        y_ticks.append(
            f'<text x="{margin_left-8}" y="{y+4:.1f}" text-anchor="end" fill="{DEFAULT_TOKENS["text_secondary"]}" font-size="12">{value:.1f}</text>'
        )
        y_ticks.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left+plot_w}" y2="{y:.1f}" stroke="{DEFAULT_TOKENS["divider"]}" stroke-width="1" />'
        )

    return f'''
<svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="{esc(spec.get("title"))}">
  {band_svg}
  {"".join(y_ticks)}
  <polyline fill="none" stroke="{DEFAULT_TOKENS["line_primary"]}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="{polyline}" />
  {"".join(point_svg)}
  {"".join(label_svg)}
  {"".join(date_svg)}
</svg>
'''


def render_supporting_facts(spec: dict) -> str:
    facts = spec.get("latest_supporting_facts", [])
    if not facts:
        return ""
    items = []
    for fact in facts:
        items.append(
            f'''
            <div class="fact-pill">
              <div class="fact-label">{esc(fact.get("label"))}</div>
              <div class="fact-value">{esc(fact.get("value_text"))}</div>
            </div>
            '''
        )
    return f'<section class="fact-grid">{"".join(items)}</section>'


def render_html(spec: dict) -> str:
    chart_type = spec.get("chart_type")
    if chart_type != "single_metric_trend_line":
        raise ValueError("first renderer only supports chart_type=single_metric_trend_line")

    chart_svg = render_single_metric_svg(spec)
    supporting = render_supporting_facts(spec)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(spec.get('title'))}</title>
  <style>
    :root {{
      --bg: {DEFAULT_TOKENS["bg"]};
      --surface: {DEFAULT_TOKENS["surface"]};
      --text-primary: {DEFAULT_TOKENS["text_primary"]};
      --text-secondary: {DEFAULT_TOKENS["text_secondary"]};
      --accent-medical: {DEFAULT_TOKENS["accent_medical"]};
      --accent-soft: {DEFAULT_TOKENS["accent_soft"]};
      --divider: {DEFAULT_TOKENS["divider"]};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top right, #EAF7F0 0, transparent 28%),
        linear-gradient(180deg, #F9FCF9 0%, var(--bg) 100%);
      color: var(--text-primary);
      font: 14px/1.5 "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      padding: 28px;
    }}
    .card {{
      max-width: 900px;
      margin: 0 auto;
      background: var(--surface);
      border: 1px solid rgba(47, 143, 107, 0.10);
      border-radius: 24px;
      box-shadow: 0 18px 60px rgba(31, 42, 36, 0.08);
      overflow: hidden;
    }}
    .hero {{
      padding: 28px 30px 18px;
      background: linear-gradient(180deg, #FFFFFF 0%, #F4FBF7 100%);
      border-bottom: 1px solid var(--divider);
    }}
    .eyebrow {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-medical);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    h1 {{
      margin: 14px 0 8px;
      font-size: 28px;
      line-height: 1.2;
    }}
    .subtitle {{
      color: var(--text-secondary);
      font-size: 15px;
    }}
    .chart-wrap {{ padding: 18px 20px 12px; }}
    .chart-svg {{ width: 100%; height: auto; display: block; }}
    .fact-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      padding: 0 20px 20px;
    }}
    .fact-pill {{
      padding: 14px 16px;
      border-radius: 18px;
      background: #FAFCFB;
      border: 1px solid var(--divider);
    }}
    .fact-label {{
      color: var(--text-secondary);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .fact-value {{
      color: var(--text-primary);
      font-size: 16px;
      font-weight: 700;
    }}
    .footer {{
      padding: 0 20px 24px;
      color: var(--text-secondary);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <article class="card">
    <header class="hero">
      <div class="eyebrow">健康趋势卡</div>
      <h1>{esc(spec.get("title"))}</h1>
      <div class="subtitle">{esc(spec.get("subtitle"))}</div>
    </header>
    <section class="chart-wrap">
      {chart_svg}
    </section>
    {supporting}
    <footer class="footer">此图用于帮助理解趋势，不替代医生诊断。</footer>
  </article>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--output-html", required=True)
    args = parser.parse_args()

    spec = load_json(Path(args.json_file))
    html_text = render_html(spec)
    Path(args.output_html).write_text(html_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
