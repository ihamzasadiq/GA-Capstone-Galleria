from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


INK = "#172033"
GOLD = "#7C3AED"
GOLD_SOFT = "#A78BFA"
GREEN = "#12B76A"
RED = "#D92D20"
BLUE = "#475467"
MUTED = "#667085"
PAPER = "rgba(0,0,0,0)"
PALETTE = [GOLD, "#A78BFA", GREEN, BLUE, "#C4B5FD", "#7F56D9", RED]


def style_figure(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font={"family": "DM Sans, Inter, Arial, sans-serif", "color": INK, "size": 12},
        title={"font": {"family": "Manrope, Inter, Arial, sans-serif", "size": 17, "color": INK}, "x": 0.03},
        margin={"l": 28, "r": 24, "t": 62, "b": 36},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hoverlabel={"bgcolor": "#FFFFFF", "font_color": INK, "bordercolor": "#EAECF0"},
    )
    fig.update_xaxes(gridcolor="rgba(16,24,40,0.07)", zeroline=False, title_font_color=MUTED)
    fig.update_yaxes(gridcolor="rgba(16,24,40,0.07)", zeroline=False, title_font_color=MUTED)
    return fig


def line_chart(data: pd.DataFrame, x: str, y: str, title: str, y_title: str = "BHD") -> go.Figure:
    fig = px.line(data, x=x, y=y, markers=True, color_discrete_sequence=[GOLD])
    fig.update_traces(line={"width": 3}, marker={"size": 7, "line": {"width": 2, "color": "#FFFFFF"}})
    fig.update_layout(title=title, xaxis_title="", yaxis_title=y_title)
    return style_figure(fig)


def horizontal_bar(
    data: pd.DataFrame,
    category: str,
    value: str,
    title: str,
    color: str | None = None,
) -> go.Figure:
    ordered = data.sort_values(value, ascending=True)
    fig = px.bar(
        ordered,
        x=value,
        y=category,
        orientation="h",
        color=color,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(marker_line_width=0, hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>")
    fig.update_layout(title=title, xaxis_title="", yaxis_title="", showlegend=color is not None)
    return style_figure(fig)


def donut_chart(data: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    fig = px.pie(data, names=names, values=values, hole=0.68, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="outside", textinfo="percent+label", sort=False)
    fig.update_layout(title=title, showlegend=False)
    return style_figure(fig)


def histogram(data: pd.DataFrame, x: str, title: str, bins: int = 12) -> go.Figure:
    fig = px.histogram(data, x=x, nbins=bins, color_discrete_sequence=[GOLD])
    fig.update_traces(marker_line_color="#FFFFFF", marker_line_width=1)
    fig.update_layout(title=title, xaxis_title="BHD", yaxis_title="Customers", bargap=0.08)
    return style_figure(fig)


def readiness_gauge(value: float, title: str, suffix: str = "%") -> go.Figure:
    value = min(max(float(value), 0), 100)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix, "font": {"family": "Georgia, serif", "size": 40, "color": INK}},
            title={"text": title, "font": {"size": 14, "color": MUTED}},
            gauge={
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": GOLD, "thickness": 0.22},
                "bgcolor": "#E8E0D4",
                "borderwidth": 0,
                "steps": [{"range": [0, 100], "color": "#E8E0D4"}],
            },
        )
    )
    return style_figure(fig, height=300)
