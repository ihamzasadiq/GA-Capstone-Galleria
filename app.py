from pathlib import Path

import streamlit as st

from components.ui import apply_design_system, render_app_footer, render_sidebar_brand


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Galleria",
    page_icon="G",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "Galleria sales and receipt workspace.",
    },
)

apply_design_system(ROOT / "assets" / "styles.css")
render_sidebar_brand()

pages = [
    st.Page("views/overview.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/receipt_ocr.py", title="Receipts", icon=":material/receipt_long:"),
    st.Page("views/brand_performance.py", title="Sales", icon=":material/bar_chart:"),
    st.Page("views/customer_insights.py", title="Customers", icon=":material/group:"),
]

current_page = st.navigation(pages, position="sidebar")
current_page.run()
render_app_footer()
