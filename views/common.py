from __future__ import annotations

from pathlib import Path

import streamlit as st

from services.data import DataBundle, load_bundle, resolve_data_dir


@st.cache_data(show_spinner=False)
def _cached_bundle(path: str) -> DataBundle:
    return load_bundle(Path(path))


def get_bundle() -> DataBundle:
    return _cached_bundle(str(resolve_data_dir()))
