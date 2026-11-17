"""FairAlt: proof-of-concept app.

Run: streamlit run app.py
"""
import streamlit as st

from ui import dashboard, nav, overview, review, theme

theme.setup()

# Hide Streamlit's own menu, footer and top colour line for viewers.
# Do not hide the whole header, or the sidebar toggle goes with it.
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden; height: 0;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

nav.PAGES.update(
    overview=st.Page(overview.render, title="Overview", icon=":material/dashboard:", default=True, url_path="overview"),
    review=st.Page(review.render, title="Review", icon=":material/fact_check:", url_path="review"),
    dashboard=st.Page(dashboard.render, title="Dashboard", icon=":material/insights:", url_path="dashboard"),
)
st.navigation({"Workspace": list(nav.PAGES.values())}, position="sidebar").run()
