"""Page setup: title, logo and the stylesheet."""
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"


def setup():
    """Must run first in app.py: set_page_config has to be the first Streamlit call."""
    st.set_page_config(page_title="FairAlt", page_icon=str(ASSETS / "icon.svg"), layout="wide")
    st.logo(str(ASSETS / "logo.svg"), size="large")
    st.markdown(f"<style>\n{(HERE / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
