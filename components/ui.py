from __future__ import annotations

from html import escape
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import streamlit as st


def _compact_html(fragment: str) -> str:
    """Remove Markdown-significant indentation from generated HTML fragments."""
    return "".join(line.strip() for line in fragment.splitlines())


def _render_html(fragment: str) -> None:
    st.markdown(_compact_html(fragment), unsafe_allow_html=True)


def apply_design_system(stylesheet: Path) -> None:
    """Load the app CSS once from a local asset."""
    if stylesheet.exists():
        st.markdown(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    mode = "Live data" if os.getenv("GALLERIA_DATA_DIR") else "Demo data"
    st.sidebar.markdown(
        _compact_html("""
        <div class="g-sidebar-brand">
          <div class="g-sidebar-mark">G</div>
          <div class="g-sidebar-title">Galleria</div>
          <div class="g-sidebar-subtitle">Store workspace</div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        _compact_html(f"""
        <div class="g-sidebar-status">
          <span class="g-status-dot"></span>
          <span>{escape(mode)}</span>
        </div>
        """),
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, description: str) -> None:
    _render_html(
        f"""
        <header class="g-page-header">
          <div class="g-page-title-row">
            <div>
              <div class="g-kicker">{escape(kicker)}</div>
              <h1 class="g-page-heading">{escape(title)}</h1>
              <p>{escape(description)}</p>
            </div>
            <div class="g-data-pill"><span></span> Verified data</div>
          </div>
        </header>
        """
    )


def hero(title: str, description: str, chips: Sequence[str]) -> None:
    chip_html = "".join(
        f'<span class="g-hero-chip">✦ {escape(chip)}</span>' for chip in chips
    )
    _render_html(
        f"""
        <section class="g-hero">
          <div class="g-hero-kicker">Galleria Concept · Bahrain</div>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
          <div class="g-hero-meta">{chip_html}</div>
        </section>
        """
    )


def metric_grid(metrics: Sequence[Mapping[str, str]]) -> None:
    cards = []
    for metric in metrics:
        cards.append(_compact_html(
            f"""
            <div class="g-metric-card">
              <div class="g-metric-label">{escape(str(metric['label']))}</div>
              <div class="g-metric-value">{escape(str(metric['value']))}</div>
              <div class="g-metric-note">{escape(str(metric.get('note', '')))}</div>
            </div>
            """
        ))
    _render_html(f'<div class="g-metric-grid">{"".join(cards)}</div>')


def section_header(title: str, description: str = "") -> None:
    _render_html(
        f"""
        <div class="g-section-heading">
          <div><h2>{escape(title)}</h2><p>{escape(description)}</p></div>
        </div>
        """
    )


def card(title: str, body: str, badge: str | None = None, tone: str = "neutral") -> None:
    badge_html = badge_markup(badge, tone) if badge else ""
    _render_html(
        f"""
        <div class="g-card">
          {badge_html}
          <h3>{escape(title)}</h3>
          <p>{escape(body)}</p>
        </div>
        """
    )


def badge_markup(text: str, tone: str = "neutral") -> str:
    valid_tones = {"success", "warning", "info", "neutral", "dark"}
    tone = tone if tone in valid_tones else "neutral"
    return f'<span class="g-badge g-badge-{tone}">{escape(str(text))}</span>'


def insight_list(items: Iterable[Mapping[str, str]]) -> None:
    rows = []
    for item in items:
        rows.append(_compact_html(
            f"""
            <div class="g-insight">
              <div class="g-insight-icon">{escape(item.get('icon', '•'))}</div>
              <div>
                <div class="g-insight-title">{escape(item['title'])}</div>
                <div class="g-insight-detail">{escape(item['detail'])}</div>
              </div>
              {badge_markup(item.get('status', 'Review'), item.get('tone', 'neutral'))}
            </div>
            """
        ))
    _render_html(f'<div class="g-card">{"".join(rows)}</div>')


def progress_card(title: str, detail: str, value: float, label: str) -> None:
    percent = min(max(float(value), 0.0), 1.0) * 100
    _render_html(
        f"""
        <div class="g-card">
          <div style="display:flex;justify-content:space-between;gap:1rem;align-items:center">
            <div><h3>{escape(title)}</h3><p>{escape(detail)}</p></div>
            <strong style="color:#191611">{escape(label)}</strong>
          </div>
          <div class="g-progress-shell" style="margin-top:1rem">
            <div class="g-progress-bar" style="width:{percent:.1f}%"></div>
          </div>
        </div>
        """
    )


def stepper(steps: Sequence[str]) -> None:
    step_html = "".join(
        _compact_html(f"""
        <div class="g-step">
          <div class="g-step-number">STEP {index:02d}</div>
          <div class="g-step-name">{escape(name)}</div>
        </div>
        """)
        for index, name in enumerate(steps, 1)
    )
    _render_html(f'<div class="g-stepper">{step_html}</div>')


def flow_cards(items: Sequence[tuple[str, str]]) -> None:
    cards = "".join(
        _compact_html(f"""
        <div class="g-flow-card">
          <div class="g-flow-number">{index:02d}</div>
          <div class="g-flow-title">{escape(title)}</div>
          <div class="g-flow-copy">{escape(copy)}</div>
        </div>
        """)
        for index, (title, copy) in enumerate(items, 1)
    )
    _render_html(f'<div class="g-flow">{cards}</div>')


def empty_state(title: str, body: str, mark: str = "✦") -> None:
    _render_html(
        f"""
        <div class="g-empty">
          <div class="g-empty-mark">{escape(mark)}</div>
          <h3>{escape(title)}</h3>
          <p>{escape(body)}</p>
        </div>
        """
    )


def callout(title: str, body: str) -> None:
    _render_html(
        f'<div class="g-callout"><strong>{escape(title)}</strong><br><span>{escape(body)}</span></div>'
    )


def render_app_footer() -> None:
    _render_html(
        """
        <footer class="g-app-footer">
          <span>Galleria Concept</span>
          <span>Built from verified receipts</span>
        </footer>
        """
    )
