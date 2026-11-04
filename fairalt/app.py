"""FairAlt: proof-of-concept app.

Run: streamlit run app.py
"""
import streamlit as st

from ui import dashboard, nav, overview, review, theme

theme.setup()

nav.PAGES.update(
    overview=st.Page(overview.render, title="Overview", icon=":material/dashboard:", default=True, url_path="overview"),
    review=st.Page(review.render, title="Review", icon=":material/fact_check:", url_path="review"),
    dashboard=st.Page(dashboard.render, title="Dashboard", icon=":material/insights:", url_path="dashboard"),
)
st.navigation({"Workspace": list(nav.PAGES.values())}, position="sidebar").run()
